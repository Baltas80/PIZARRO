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


def test_block_round_trip_is_deterministic():
    g = genesis()
    assert block_to_dict(g) == block_to_dict(block_from_dict(block_to_dict(g)))


def test_heavier_fork_becomes_selected_tip():
    g = genesis()
    chain = Chain(g)
    weak = mine_block(g, (), difficulty=8, timestamp=1)
    strong1 = mine_block(g, (), difficulty=10, timestamp=2)
    strong2 = mine_block(strong1, (), difficulty=10, timestamp=3)
    chain.add_block(weak)
    chain.add_block(strong1)
    chain.add_block(strong2)
    assert chain.tip.header.hash == strong2.header.hash
    assert weak.header.hash in chain.blocks


def test_two_node_sync_transfers_chain():
    async def run():
        g = genesis()
        source_chain = Chain(g)
        child = mine_block(g, (), difficulty=8, timestamp=1)
        source_chain.add_block(child)
        source = DevNode(source_chain)
        target = DevNode(Chain(g))
        port = await source.start()
        try:
            accepted = await target.sync_from("127.0.0.1", port)
            assert accepted == 1
            assert target.chain.tip.header.hash == child.header.hash
        finally:
            await source.stop()

    asyncio.run(run())
