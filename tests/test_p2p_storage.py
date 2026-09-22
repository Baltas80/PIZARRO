import asyncio

from pizarro.core import Block, BlockHeader, Chain, GENESIS_HASH, merkle_root
from pizarro.node import DevNode, Mempool, encode_message
from pizarro.storage import load_blocks, save_chain


def genesis():
    nonce = 0
    while True:
        block = Block(BlockHeader(0, GENESIS_HASH, merkle_root(()), 0, 8, nonce), ())
        try:
            block.validate()
            return block
        except ValueError:
            nonce += 1


def test_message_size_limit():
    try:
        encode_message({"x": "a" * (1 << 20)})
    except ValueError:
        return
    raise AssertionError("oversized message accepted")


def test_persistence_round_trip(tmp_path):
    g = genesis()
    path = tmp_path / "chain.json"
    save_chain(path, [g])
    blocks = load_blocks(path)
    assert blocks[0].header.hash == g.header.hash


def test_two_nodes_can_ping():
    async def run():
        node_a = DevNode(Chain(genesis()))
        node_b = DevNode(Chain(genesis()))
        port = await node_b.start()
        try:
            assert await node_a.ping("127.0.0.1", port)
        finally:
            await node_b.stop()
    asyncio.run(run())


def test_mempool_rejects_wrong_chain():
    from pizarro.core import Transaction
    pool = Mempool()
    bad = Transaction("a", "b", 1, 0, "OTHER")
    try:
        pool.add(bad)
    except ValueError:
        return
    raise AssertionError("wrong-chain transaction accepted")
