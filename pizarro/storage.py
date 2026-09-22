from __future__ import annotations

import json
from pathlib import Path

from .core import Block, BlockHeader, Transaction


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
    blocks: list[Block] = []
    for item in raw:
        h = item["header"]
        header = BlockHeader(**h)
        txs = tuple(Transaction(**tx) for tx in item["transactions"])
        blocks.append(Block(header, txs))
    return blocks
