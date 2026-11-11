import numpy as np
import pandas as pd
from markets import CAC, NASDAQ
from engine import compute


def sample_bars(volume):
    idx = pd.date_range('2026-11-10 09:05', periods=45, freq='5min', tz=CAC.timezone)
    close = np.linspace(8000, 8030, len(idx))
    return pd.DataFrame({'open':close,'high':close+2,'low':close-2,
                         'close':close,'volume':volume},index=idx)


def test_cac_uses_index_not_etf():
    assert CAC.symbol == '^FCHI'
    assert NASDAQ.symbol == 'QQQ'


def test_no_index_volume_means_no_mer_or_signal():
    bars = sample_bars(np.full(45, np.nan))
    result = compute(bars, market=CAC)
    assert result.MER.isna().all()


def test_proxy_stock_volume_can_enable_mer():
    bars = sample_bars(np.full(45, 1000000))
    result = compute(bars, market=CAC)
    assert result.MER.notna().any()

