"""Public Yahoo data adapter. Best effort, NOT an exchange-grade live feed."""
import pandas as pd
import yfinance as yf

# Representative Nasdaq-100 members, not complete point-in-time membership.
LEADERS = ['AAPL','MSFT','NVDA','AMZN','META','GOOGL','GOOG','AVGO','TSLA','COST','NFLX','AMD','ADBE','PEP','CSCO','TMUS','INTC','AMAT','QCOM','INTU','TXN','ISRG','BKNG','MU','PANW','ADP','LRCX','KLAC','CRWD']
NY = 'America/New_York'

def _to_bars(df):
    if df is None or df.empty:
        raise ValueError('Le fournisseur ne retourne aucune cotation. Réessayez plus tard.')
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert(NY) + pd.Timedelta(minutes=5)
    df = df.between_time('09:35','16:00').sort_index()
    # Yahoo labels bars at START. Exclude current unfinished 5-minute bar.
    now = pd.Timestamp.now(tz=NY)
    df = df[df.index <= now]
    return df.loc[:, ['open','high','low','close','volume']].dropna()

def fetch_qqq(days=5):
    raw = yf.download('QQQ', period=f'{days}d', interval='5m', auto_adjust=True,
                      progress=False, threads=False, timeout=18)
    return _to_bars(raw)

def fetch_leaders(days=5):
    raw = yf.download(' '.join(LEADERS), period=f'{days}d', interval='5m',
                      auto_adjust=True, progress=False, threads=True, timeout=25)
    if raw is None or raw.empty:
        raise ValueError('Impossible de charger les constituants')
    if not isinstance(raw.columns, pd.MultiIndex):
        raise ValueError('Format de réponse inattendu pour les constituants')
    close = raw['Close'].copy()
    if close.index.tz is None: close.index = close.index.tz_localize('UTC')
    close.index = close.index.tz_convert(NY) + pd.Timedelta(minutes=5)
    close = close.between_time('09:35','16:00')
    close = close[close.index <= pd.Timestamp.now(tz=NY)]
    close = close.dropna(axis=1, how='all')
    if close.shape[1] < 20:
        raise ValueError(f'Couverture insuffisante : {close.shape[1]} titres sur {len(LEADERS)}')
    return close
