import asyncio

import pytest

from pizarro.core import Block, BlockHeader, Chain, GENESIS_HASH, merkle_root
from pizarro.node import MAX_BLOCKS_PER_RESPONSE, DevNode, encode_message


def genesis():
    nonce = 0
    while True:
        block = Block(BlockHeader(0, GENESIS_HASH, merkle_root(()), 0, 8, nonce), ())
        try:
            block.validate()
            return block
        except ValueError:
            nonce += 1


def test_blocks_message_limit():
    async def run():
        node = DevNode(Chain(genesis()))
        with pytest.raises(ValueError, match="too many blocks"):
            await node.handle_message({"type": "blocks", "blocks": [{}] * (MAX_BLOCKS_PER_RESPONSE + 1)}, None)

    asyncio.run(run())


def test_send_block_rejects_unknown_parent_locally():
    async def run():
        node = DevNode(Chain(genesis()))
        block = Block(BlockHeader(1, "1" * 64, merkle_root(()), 1, 8, 0), ())
        with pytest.raises(ValueError, match="unknown parent"):
            await node.send_block("127.0.0.1", 1, block)

    asyncio.run(run())


def test_oversized_message_rejected():
    with pytest.raises(ValueError, match="message too large"):
        encode_message({"payload": "x" * (1 << 20)})
