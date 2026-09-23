from pizarro.core import Block, BlockHeader, Chain, GENESIS_HASH, merkle_root, mine_block
from pizarro.storage import load_chain, save_chain


def genesis():
    nonce = 0
    while True:
        block = Block(BlockHeader(0, GENESIS_HASH, merkle_root(()), 0, 8, nonce), ())
        try:
            block.validate()
            return block
        except ValueError:
            nonce += 1


def test_chain_recovers_and_reselects_heavier_fork(tmp_path):
    g = genesis()
    chain = Chain(g)
    a1 = mine_block(g, (), difficulty=8, timestamp=1)
    a2 = mine_block(a1, (), difficulty=8, timestamp=2)
    chain.add_block(a1)
    chain.add_block(a2)

    b1 = mine_block(g, (), difficulty=9, timestamp=3)
    b2 = mine_block(b1, (), difficulty=9, timestamp=4)
    b3 = mine_block(b2, (), difficulty=9, timestamp=5)
    chain.add_block(b1)
    chain.add_block(b2)
    chain.add_block(b3)
    assert chain.tip.header.hash == b3.header.hash

    path = tmp_path / "chain.json"
    save_chain(path, [g, a1, a2, b1, b2, b3])
    recovered = load_chain(path)
    assert recovered.tip.header.hash == b3.header.hash
    assert recovered.work[b3.header.hash] > recovered.work[a2.header.hash]


def test_corrupt_persisted_block_is_rejected(tmp_path):
    g = genesis()
    path = tmp_path / "chain.json"
    save_chain(path, [g])
    data = path.read_text(encoding="utf-8").replace('"height":0', '"height":1')
    path.write_text(data, encoding="utf-8")
    try:
        load_chain(path)
    except ValueError:
        return
    raise AssertionError("corrupt persisted chain was accepted")
