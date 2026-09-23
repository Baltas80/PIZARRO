from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from .core import Block, BlockHeader, Chain, Transaction

MAX_MESSAGE_BYTES = 1 << 20
MAX_BLOCKS_PER_RESPONSE = 256


def encode_message(message: dict[str, Any]) -> bytes:
    payload = json.dumps(message, sort_keys=True, separators=(",", ":")).encode()
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("message too large")
    return payload + b"\n"


def transaction_to_dict(tx: Transaction) -> dict[str, Any]:
    return tx.to_dict()


def transaction_from_dict(data: dict[str, Any]) -> Transaction:
    tx = Transaction(
        sender=str(data["sender"]),
        recipient=str(data["recipient"]),
        amount=int(data["amount"]),
        nonce=int(data["nonce"]),
        chain_id=str(data.get("chain_id", "")),
    )
    tx.validate()
    return tx


def block_to_dict(block: Block) -> dict[str, Any]:
    return {
        "header": block.header.to_dict(),
        "transactions": [transaction_to_dict(tx) for tx in block.transactions],
    }


def block_from_dict(data: dict[str, Any]) -> Block:
    if not isinstance(data, dict):
        raise ValueError("invalid block payload")
    header_data = data["header"]
    if not isinstance(header_data, dict):
        raise ValueError("invalid block header")
    header = BlockHeader(
        height=int(header_data["height"]),
        previous_hash=str(header_data["previous_hash"]),
        merkle_root=str(header_data["merkle_root"]),
        timestamp=int(header_data["timestamp"]),
        difficulty=int(header_data["difficulty"]),
        nonce=int(header_data["nonce"]),
        chain_id=str(header_data.get("chain_id", "")),
    )
    raw_txs = data.get("transactions", [])
    if not isinstance(raw_txs, list):
        raise ValueError("invalid transactions payload")
    if len(raw_txs) > 10_000:
        raise ValueError("too many transactions")
    txs = tuple(transaction_from_dict(tx) for tx in raw_txs)
    return Block(header, txs)


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
            if not isinstance(msg, dict):
                raise ValueError("invalid message")
            await self.handle_message(msg, writer)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError,
                asyncio.LimitOverrunError, asyncio.IncompleteReadError):
            try:
                writer.write(encode_message({"type": "error", "error": "invalid_message"}))
                await writer.drain()
            except (ConnectionError, ValueError):
                pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def _send(self, writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
        writer.write(encode_message(message))
        await writer.drain()

    def _canonical_chain(self) -> list[Block]:
        """Return the selected tip's ancestors in genesis-to-tip order."""
        blocks: list[Block] = []
        current = self.chain.tip
        while current.header.height > 0:
            blocks.append(current)
            current = self.chain.blocks[current.header.previous_hash]
        blocks.append(current)
        blocks.reverse()
        return blocks

    async def handle_message(self, msg: dict[str, Any], writer: asyncio.StreamWriter) -> None:
        kind = msg.get("type")
        if kind == "ping":
            await self._send(writer, {"type": "pong"})
        elif kind == "status":
            tip = self.chain.tip
            await self._send(
                writer,
                {"type": "status", "height": tip.header.height, "work": self.chain.work[tip.header.hash]},
            )
        elif kind == "getblocks":
            start_height = max(0, int(msg.get("from_height", 0)))
            blocks = [b for b in self._canonical_chain() if b.header.height >= start_height]
            blocks = blocks[:MAX_BLOCKS_PER_RESPONSE]
            await self._send(writer, {"type": "blocks", "blocks": [block_to_dict(b) for b in blocks]})
        elif kind == "block":
            block = block_from_dict(msg["block"])
            self.chain.add_block(block)
            await self._send(writer, {"type": "accepted", "hash": block.header.hash})
        elif kind == "blocks":
            raw_blocks = msg.get("blocks", [])
            if not isinstance(raw_blocks, list) or len(raw_blocks) > MAX_BLOCKS_PER_RESPONSE:
                raise ValueError("too many blocks")
            for data in raw_blocks:
                self.chain.add_block(block_from_dict(data))
            await self._send(writer, {"type": "accepted", "height": self.chain.tip.header.height})
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

    async def sync_from(self, host: str, port: int) -> int:
        """Fetch and validate the remote canonical chain from our current height."""
        reader, writer = await asyncio.open_connection(host, port, limit=MAX_MESSAGE_BYTES)
        try:
            start = self.chain.tip.header.height + 1
            writer.write(encode_message({"type": "getblocks", "from_height": start}))
            await writer.drain()
            raw = await reader.readline()
            response = json.loads(raw)
            if response.get("type") != "blocks":
                raise ValueError("peer did not return blocks")
            remote_blocks = response.get("blocks", [])
            if not isinstance(remote_blocks, list) or len(remote_blocks) > MAX_BLOCKS_PER_RESPONSE:
                raise ValueError("too many blocks")
            accepted = 0
            for data in remote_blocks:
                block = block_from_dict(data)
                before = len(self.chain.blocks)
                self.chain.add_block(block)
                accepted += len(self.chain.blocks) - before
            return accepted
        finally:
            writer.close()
            await writer.wait_closed()

    async def send_block(self, host: str, port: int, block: Block) -> bool:
        """Send one block; require its parent to exist locally before transmitting."""
        parent = self.chain.blocks.get(block.header.previous_hash)
        if parent is None:
            raise ValueError("unknown parent")
        block.validate(parent)
        reader, writer = await asyncio.open_connection(host, port, limit=MAX_MESSAGE_BYTES)
        try:
            writer.write(encode_message({"type": "block", "block": block_to_dict(block)}))
            await writer.drain()
            raw = await reader.readline()
            return json.loads(raw).get("type") == "accepted"
        finally:
            writer.close()
            await writer.wait_closed()
