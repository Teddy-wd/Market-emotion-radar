
import numpy as np
import pandas as pd

from dominance import detect, event_study, ShiftConfig


def sample_data():
    """Crée une séance fictive de 5 minutes."""
    idx = pd.date_range(
        "2026-11-10 09:35",
        periods=20,
        freq="5min",
        tz="America/New_York",
    )

    close = np.linspace(100, 105, len(idx))

    return pd.DataFrame(
        {
            "MER": np.linspace(35, 70, len(idx)),
            "breadth": np.full(len(idx), 0.5),
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.full(len(idx), 10000),
        },
        index=idx,
    )


def test_detector_creates_columns():
    result = detect(sample_data())

    assert "shift_state" in result.columns
    assert "shift_signal" in result.columns
    assert "delta_10m" in result.columns
    assert "rvol" in result.columns


def test_mer_signal_values():
    result = detect(sample_data())

    assert result["shift_signal"].isin(
        ["LONG", "SHORT", "none"]
    ).all()


def test_event_study_output():
    result = detect(sample_data())

    summary, details = event_study(result)

    assert "hit_rate_net" in summary.columns
    assert "mean_net_bps" in summary.columns
    assert isinstance(details, pd.DataFrame)


def test_no_signal_on_first_bar():
    result = detect(sample_data())

    assert result["shift_signal"].iloc[0] == "none"


def test_missing_columns_raise_error():
    incomplete = sample_data().drop(columns=["volume"])

    try:
        detect(incomplete)
        assert False, "Une erreur était attendue"
    except ValueError:
        pass
