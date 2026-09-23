from __future__ import annotations

import json
from pathlib import Path

from .core import Block, BlockHeader, Chain, Transaction


def save_chain(path: str | Path, blocks: list[Block]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    data = []
    for block in blocks:
        data.append({
            "header": block.header.to_dict(),
            "transactions": [tx.to_dict() for tx in block.transactions],
        })
    tmp.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    tmp.replace(target)


def load_blocks(path: str | Path) -> list[Block]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("chain file must contain a non-empty block list")
    blocks: list[Block] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("invalid block record")
        h = item["header"]
        txs = tuple(Transaction(**tx) for tx in item["transactions"])
        blocks.append(Block(BlockHeader(**h), txs))
    return blocks


def load_chain(path: str | Path) -> Chain:
    """Load and validate a persisted chain before exposing it to consensus."""
    blocks = load_blocks(path)
    blocks.sort(key=lambda block: (block.header.height, block.header.hash))
    genesis = blocks[0]
    if genesis.header.height != 0:
        raise ValueError("chain file does not start with genesis")
    chain = Chain(genesis)
    for block in blocks[1:]:
        chain.add_block(block)
    return chain
