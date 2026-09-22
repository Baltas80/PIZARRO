from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from .core import Block, Chain, Transaction

MAX_MESSAGE_BYTES = 1 << 20


def encode_message(message: dict[str, Any]) -> bytes:
    payload = json.dumps(message, sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("message too large")
    return payload + b"\n"


@dataclass
class Mempool:
    transactions: dict[str, Transaction] = field(default_factory=dict)

    def add(self, tx: Transaction) -> str:
        tx.validate()
        self.transactions.setdefault(tx.txid, tx)
        return tx.txid

    def remove(self, txids: set[str]) -> None:
        for txid in txids:
            self.transactions.pop(txid, None)


class DevNode:
    """Small asyncio P2P node for development and consensus integration tests."""

    def __init__(self, chain: Chain):
        self.chain = chain
        self.mempool = Mempool()
        self.peers: set[tuple[str, int]] = set()
        self.server: asyncio.AbstractServer | None = None

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> int:
        self.server = await asyncio.start_server(self._handle_peer, host, port, limit=MAX_MESSAGE_BYTES)
        return int(self.server.sockets[0].getsockname()[1])

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    async def _handle_peer(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await reader.readline()
            if not raw or len(raw) > MAX_MESSAGE_BYTES:
                return
            msg = json.loads(raw)
            await self.handle_message(msg, writer)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle_message(self, msg: dict[str, Any], writer: asyncio.StreamWriter) -> None:
        kind = msg.get("type")
        if kind == "ping":
            writer.write(encode_message({"type": "pong"}))
            await writer.drain()
        elif kind == "status":
            tip = self.chain.tip
            writer.write(encode_message({"type": "status", "height": tip.header.height, "work": self.chain.work[tip.header.hash]}))
            await writer.drain()
        else:
            raise ValueError("unsupported message")

    async def ping(self, host: str, port: int) -> bool:
        reader, writer = await asyncio.open_connection(host, port, limit=MAX_MESSAGE_BYTES)
        try:
            writer.write(encode_message({"type": "ping"}))
            await writer.drain()
            raw = await reader.readline()
            return json.loads(raw).get("type") == "pong"
        finally:
            writer.close()
            await writer.wait_closed()
