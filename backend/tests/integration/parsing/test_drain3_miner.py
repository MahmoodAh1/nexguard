"""Integration tests for the Drain3 template miner adapter."""

from __future__ import annotations

import pytest

from nexguard.infrastructure.parsing.drain3_miner import Drain3TemplateMiner

pytestmark = pytest.mark.integration

_RECV_A = "081109 200006 730 INFO dfs.DataNode$DataXceiver: Receiving block blk_111 src: /10.1.1.1:5 dest: /10.1.1.1:50010"  # noqa: E501
_RECV_B = "081109 200007 731 INFO dfs.DataNode$DataXceiver: Receiving block blk_-222 src: /10.2.2.2:9 dest: /10.2.2.2:50010"  # noqa: E501
_STORED = "081109 200010 500 INFO dfs.FSNamesystem: BLOCK* NameSystem.addStoredBlock: blockMap updated: 10.3.3.3:50010 is added to blk_333 size 42"  # noqa: E501


def test_lines_differing_only_in_variables_share_a_template() -> None:
    miner = Drain3TemplateMiner()
    first = miner.mine(_RECV_A)
    second = miner.mine(_RECV_B)

    assert first.event_id == second.event_id
    assert "<BLOCK_ID>" in first.template
    assert "<IP>" in first.template


def test_structurally_different_lines_get_distinct_event_ids() -> None:
    miner = Drain3TemplateMiner()
    receiving = miner.mine(_RECV_A)
    stored = miner.mine(_STORED)

    assert receiving.event_id != stored.event_id


def test_event_ids_are_stable_across_repeat_calls() -> None:
    miner = Drain3TemplateMiner()
    first = miner.mine(_RECV_A)
    miner.mine(_STORED)
    again = miner.mine(_RECV_A)
    assert first.event_id == again.event_id


def test_vocabulary_reflects_mined_templates() -> None:
    miner = Drain3TemplateMiner()
    miner.mine(_RECV_A)
    miner.mine(_RECV_B)
    miner.mine(_STORED)

    vocab = miner.vocabulary()
    assert len(vocab) == 2  # receiving (shared) + stored
    event_ids = {int(t.event_id) for t in vocab}
    assert len(event_ids) == 2
