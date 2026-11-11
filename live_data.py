"""Yahoo Finance 5-minute data; best-effort, potentially delayed."""
import pandas as pd
import yfinance as yf
from markets import Market, NASDAQ


def _close_index(idx, market: Market):
    if idx.tz is None:
        idx = idx.tz_localize('UTC')
    return idx.tz_convert(market.timezone) + pd.Timedelta(minutes=5)


def _to_bars(df, market: Market):
    if df is None or df.empty:
        raise ValueError(f'Aucune donnée Yahoo pour {market.symbol}.')
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    df.index = _close_index(df.index, market)
    df = df.between_time(market.start, market.end).sort_index()
    df = df[df.index <= pd.Timestamp.now(tz=market.timezone)]
    for col in ['open','high','low','close']:
        if col not in df.columns: raise ValueError(f'Colonne {col} absente pour {market.symbol}')
    if 'volume' not in df.columns: df['volume'] = float('nan')
    return df.loc[:, ['open','high','low','close','volume']].dropna(subset=['open','high','low','close'])


def fetch_price(market: Market, days=5):
    raw = yf.download(market.symbol, period=f'{days}d', interval='5m',
                      auto_adjust=True, progress=False, threads=False, timeout=20)
    return _to_bars(raw, market)


def fetch_constituents(market: Market, days=5):
    """Return (close matrix, aggregate stock volume) for eligible 5m stock bars.

    Aggregated volumes are NOT index volume. Coverage must meet the threshold
    at each timestamp; absent data remain NaN rather than silently zero.
    """
    raw = yf.download(list(market.leaders), period=f'{days}d', interval='5m',
                      auto_adjust=True, progress=False, threads=True, timeout=30)
    if raw is None or raw.empty or not isinstance(raw.columns, pd.MultiIndex):
        raise ValueError('Données de constituants indisponibles.')
    if 'Close' not in raw.columns.get_level_values(0) or 'Volume' not in raw.columns.get_level_values(0):
        raise ValueError('Prix ou volumes des constituants absents.')
    closes = raw['Close'].copy()
    volumes = raw['Volume'].copy()
    closes.index = _close_index(closes.index, market)
    volumes.index = _close_index(volumes.index, market)
    closes = closes.between_time(market.start, market.end)
    volumes = volumes.between_time(market.start, market.end)
    now = pd.Timestamp.now(tz=market.timezone)
    closes = closes.loc[closes.index <= now].dropna(axis=1, how='all')
    volumes = volumes.loc[volumes.index <= now].reindex(columns=closes.columns)
    if closes.shape[1] < market.min_breadth_count:
        raise ValueError(f'Couverture insuffisante : {closes.shape[1]} titres disponibles.')
    eligible = volumes.where((volumes > 0) & closes.notna())
    count = eligible.notna().sum(axis=1)
    aggregate = eligible.sum(axis=1, min_count=market.min_breadth_count).where(count >= market.min_breadth_count)
    return closes, aggregate


def fetch_leaders(market: Market, days=5):
    """Backward compatible close-only accessor."""
    return fetch_constituents(market, days)[0]

# Backward compatibility with v0.3
LEADERS = list(NASDAQ.leaders)
def fetch_qqq(days=5):
    return fetch_price(NASDAQ, days)
