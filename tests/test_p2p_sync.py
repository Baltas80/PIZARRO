import asyncio

from pizarro.core import Block, BlockHeader, Chain, GENESIS_HASH, merkle_root, mine_block
from pizarro.node import DevNode, block_from_dict, block_to_dict


def genesis():
    nonce = 0
    while True:
        block = Block(BlockHeader(0, GENESIS_HASH, merkle_root(()), 0, 8, nonce), ())
        try:
            block.validate()
            return block
        except ValueError:
            nonce += 1


def test_block_wire_round_trip():
    g = genesis()
    b = mine_block(g, (), difficulty=8, timestamp=1)
    restored = block_from_dict(block_to_dict(b))
    assert restored.header.hash == b.header.hash
    assert restored.transactions == b.transactions


def test_two_nodes_sync_blocks():
    async def run():
        g = genesis()
        source_chain = Chain(g)
        b1 = mine_block(source_chain.tip, (), difficulty=8, timestamp=1)
        source_chain.add_block(b1)
        b2 = mine_block(source_chain.tip, (), difficulty=8, timestamp=2)
        source_chain.add_block(b2)

        source = DevNode(source_chain)
        target = DevNode(Chain(g))
        port = await source.start()
        try:
            assert await target.sync_from("127.0.0.1", port) == 2
            assert target.chain.tip.header.hash == b2.header.hash
        finally:
            await source.stop()

    asyncio.run(run())


def test_node_propagates_a_valid_block():
    async def run():
        g = genesis()
        source_chain = Chain(g)
        block = mine_block(source_chain.tip, (), difficulty=8, timestamp=1)
        source_chain.add_block(block)
        source = DevNode(source_chain)
        target = DevNode(Chain(g))
        port = await target.start()
        try:
            assert await source.send_block("127.0.0.1", port, block)
            assert target.chain.tip.header.hash == block.header.hash
        finally:
            await target.stop()

    asyncio.run(run())
