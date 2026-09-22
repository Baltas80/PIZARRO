import pytest

from pizarro.core import Block, BlockHeader, Chain, GENESIS_HASH, Transaction, merkle_root, mine_block


def genesis():
    header = BlockHeader(0, GENESIS_HASH, merkle_root(()), 0, 8, 0)
    nonce = 0
    while True:
        header = BlockHeader(0, GENESIS_HASH, merkle_root(()), 0, 8, nonce)
        block = Block(header, ())
        try:
            block.validate()
            return block
        except ValueError:
            nonce += 1


def test_genesis_and_child_validate():
    g = genesis()
    c = Chain(g)
    b = mine_block(g, (), difficulty=8, timestamp=1)
    c.add_block(b)
    assert c.tip.header.height == 1


def test_wrong_chain_id_rejected():
    tx = Transaction("a", "b", 1, 0, chain_id="OTHER")
    with pytest.raises(ValueError, match="chain_id"):
        tx.validate()


def test_unknown_parent_rejected():
    g = genesis()
    c = Chain(g)
    fake = Block(BlockHeader(1, "1" * 64, merkle_root(()), 1, 8, 0), ())
    with pytest.raises(ValueError, match="unknown parent"):
        c.add_block(fake)


def test_invalid_merkle_root_rejected():
    g = genesis()
    b = mine_block(g, (), difficulty=8, timestamp=1)
    bad = Block(BlockHeader(1, b.header.previous_hash, "1" * 64, 1, 8, b.header.nonce), ())
    with pytest.raises(ValueError, match="merkle"):
        bad.validate(g)


def test_cumulative_work_selects_heavier_chain():
    g = genesis()
    c = Chain(g)
    weak = mine_block(g, (), difficulty=8, timestamp=1)
    c.add_block(weak)
    strong = mine_block(g, (), difficulty=10, timestamp=2)
    c.add_block(strong)
    assert c.tip.header.hash == strong.header.hash
