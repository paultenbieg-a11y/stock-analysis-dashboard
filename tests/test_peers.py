import numpy as np

from stockanalysis.data import snapshot_from_info
from stockanalysis.peers import (
    build_peer_frame,
    peer_percentiles,
    percentile_rank,
    positioning_text,
)


def test_percentile_rank():
    assert percentile_rank([1, 2, 3, 4, 5], 4) == (3 + 0.5) / 5
    assert percentile_rank([1, 2, 3, 4, 5], 1) == 0.5 / 5
    assert np.isnan(percentile_rank([1, 2, 3], 2))          # too few values
    assert np.isnan(percentile_rank([1, 2, 3, 4], np.nan))  # nan subject


def test_snapshot_from_info(info):
    row = snapshot_from_info("TEST", info)
    assert row["symbol"] == "TEST"
    assert row["trailing_pe"] == 30.0
    assert row["fcf_yield"] == 30e9 / 1.8e12
    assert row["operating_margin"] == 0.30


def test_build_peer_frame_subject_first(info, peer_rows):
    subject = snapshot_from_info("TEST", info)
    frame = build_peer_frame(subject, peer_rows)
    assert frame.iloc[0]["symbol"] == "TEST"
    caps = frame.iloc[1:]["market_cap"].tolist()
    assert caps == sorted(caps, reverse=True)


def test_percentiles_and_positioning(info, peer_rows):
    subject = snapshot_from_info("TEST", info)
    ranks = peer_percentiles(subject, peer_rows)
    for value in ranks.values():
        assert np.isnan(value) or 0 <= value <= 1
    text = positioning_text(subject, peer_rows)
    assert "TEST" in text
    assert "percentile" in text


def test_positioning_empty_with_few_peers(info, peer_rows):
    subject = snapshot_from_info("TEST", info)
    assert positioning_text(subject, peer_rows[:2]) == ""
