from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Iterable

CHAIN_ID = "PIZARRO-MAINNET-V1"
MAX_SUPPLY = 1_100_000_000
FOUNDER_ALLOCATION = 100_000_000
MINING_ALLOCATION = 1_000_000_000
GENESIS_HASH = "0" * 64
MAX_TX_BYTES = 16 * 1024
MAX_BLOCK_TXS = 10_000


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def merkle_root(txids: Iterable[str]) -> str:
    layer = list(txids)
    if not layer:
        return GENESIS_HASH
    while len(layer) > 1:
        if len(layer) & 1:
            layer.append(layer[-1])
        layer = [sha256_hex(bytes.fromhex(layer[i] + layer[i + 1])) for i in range(0, len(layer), 2)]
    return layer[0]


@dataclass(frozen=True)
class Transaction:
    sender: str
    recipient: str
    amount: int
    nonce: int
    chain_id: str = CHAIN_ID

    def validate(self) -> None:
        if self.chain_id != CHAIN_ID:
            raise ValueError("wrong chain_id")
        if not self.sender or not self.recipient:
            raise ValueError("sender and recipient are required")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.nonce < 0:
            raise ValueError("nonce must be non-negative")
        if len(self.to_bytes()) > MAX_TX_BYTES:
            raise ValueError("transaction too large")

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "nonce": self.nonce,
        }

    def to_bytes(self) -> bytes:
        return _canonical(self.to_dict())

    @property
    def txid(self) -> str:
        return sha256_hex(self.to_bytes())


@dataclass(frozen=True)
class BlockHeader:
    height: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    difficulty: int
    nonce: int
    chain_id: str = CHAIN_ID

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "height": self.height,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "difficulty": self.difficulty,
            "nonce": self.nonce,
        }

    def to_bytes(self) -> bytes:
        return _canonical(self.to_dict())

    @property
    def hash(self) -> str:
        return sha256_hex(self.to_bytes())


@dataclass(frozen=True)
class Block:
    header: BlockHeader
    transactions: tuple[Transaction, ...] = field(default_factory=tuple)

    def validate(self, parent: Block | None = None) -> None:
        h = self.header
        if h.chain_id != CHAIN_ID:
            raise ValueError("wrong chain_id")
        if h.height == 0:
            if h.previous_hash != GENESIS_HASH:
                raise ValueError("invalid genesis parent")
        elif parent is not None:
            if h.previous_hash != parent.header.hash:
                raise ValueError("invalid previous_hash")
            if h.height != parent.header.height + 1:
                raise ValueError("invalid height")
        if len(self.transactions) > MAX_BLOCK_TXS:
            raise ValueError("too many transactions")
        for tx in self.transactions:
            tx.validate()
        if merkle_root(tx.txid for tx in self.transactions) != h.merkle_root:
            raise ValueError("invalid merkle root")
        target = 1 << (256 - min(max(h.difficulty, 1), 255))
        if int(h.hash, 16) >= target:
            raise ValueError("invalid proof of work")

    @property
    def work(self) -> int:
        target = 1 << (256 - min(max(self.header.difficulty, 1), 255))
        return max(1, (1 << 256) // target)


class Chain:
    def __init__(self, genesis: Block):
        genesis.validate()
        self.blocks: dict[str, Block] = {genesis.header.hash: genesis}
        self.tips: set[str] = {genesis.header.hash}
        self.work: dict[str, int] = {genesis.header.hash: genesis.work}

    @property
    def tip(self) -> Block:
        return max((self.blocks[h] for h in self.tips), key=lambda b: (self.work[b.header.hash], b.header.hash))

    def add_block(self, block: Block) -> None:
        h = block.header.hash
        if h in self.blocks:
            return
        parent = self.blocks.get(block.header.previous_hash)
        if parent is None:
            raise ValueError("unknown parent")
        block.validate(parent)
        self.blocks[h] = block
        self.work[h] = self.work[parent.header.hash] + block.work
        self.tips.discard(parent.header.hash)
        self.tips.add(h)


def mine_block(parent: Block, transactions: Iterable[Transaction], difficulty: int = 8, timestamp: int = 0) -> Block:
    txs = tuple(transactions)
    root = merkle_root(tx.txid for tx in txs)
    nonce = 0
    while True:
        header = BlockHeader(parent.header.height + 1, parent.header.hash, root, timestamp, difficulty, nonce)
        block = Block(header, txs)
        try:
            block.validate(parent)
            return block
        except ValueError as exc:
            if str(exc) != "invalid proof of work":
                raise
        nonce += 1
