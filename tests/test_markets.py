
import numpy as np
import pandas as pd
import pytest

from markets import CAC, NASDAQ
from engine import compute
from dominance import detect, event_study


@pytest.mark.parametrize("market", [CAC, NASDAQ])
def test_market_sessions_and_signal_pipeline(market):
    day = "2026-11-10"

    idx = pd.date_range(
        f"{day} {market.start}",
        periods=45,
        freq="5min",
        tz=market.timezone,
    )

    close = (
        np.linspace(100, 104, len(idx))
        + 0.12 * np.sin(np.arange(len(idx)))
    )

    df = pd.DataFrame(
        {
            "open": close - 0.03,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(len(idx), 10000),
        },
        index=idx,
    )

    result = detect(
        compute(df, market=market),
        timezone=market.timezone,
    )

    assert len(result) > 15
    assert result.MER.notna().any()

    assert {
        "shift_state",
        "shift_signal",
        "rvol",
        "delta_10m",
    }.issubset(result.columns)

    assert result.shift_signal.isin(
        ["none", "LONG", "SHORT"]
    ).all()

    summary, details = event_study(
        result,
        timezone=market.timezone,
    )

    assert len(summary) == 8
    assert isinstance(details, pd.DataFrame)


def test_cac_not_filtered_by_us_hours():
    idx = pd.date_range(
        "2026-11-10 09:05",
        periods=40,
        freq="5min",
        tz=CAC.timezone,
    )

    close = np.linspace(50, 53, len(idx))

    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": 10000,
        },
        index=idx,
    )

    assert len(compute(df, market=CAC)) == 40
    assert len(compute(df, market=NASDAQ)) == 0
