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
    return df.loc[:, ['open','high','low','close','volume']].dropna()


def fetch_price(market: Market, days=5):
    raw = yf.download(market.symbol, period=f'{days}d', interval='5m',
                      auto_adjust=True, progress=False, threads=False, timeout=20)
    return _to_bars(raw, market)


def fetch_leaders(market: Market, days=5):
    raw = yf.download(list(market.leaders), period=f'{days}d', interval='5m',
                      auto_adjust=True, progress=False, threads=True, timeout=30)
    if raw is None or raw.empty or not isinstance(raw.columns, pd.MultiIndex):
        raise ValueError('Données de constituants indisponibles.')
    close = raw['Close'].copy()
    close.index = _close_index(close.index, market)
    close = close.between_time(market.start, market.end)
    close = close[close.index <= pd.Timestamp.now(tz=market.timezone)]
    close = close.dropna(axis=1, how='all')
    if close.shape[1] < market.min_breadth_count:
        raise ValueError(f'Couverture insuffisante : {close.shape[1]} titres disponibles.')
    return close

# Backward compatibility with v0.3
LEADERS = list(NASDAQ.leaders)
def fetch_qqq(days=5):
    return fetch_price(NASDAQ, days)
