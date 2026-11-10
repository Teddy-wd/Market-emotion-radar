"""Market Emotion Radar: causally computed 5-minute indicators."""
import numpy as np
import pandas as pd

WEIGHTS = {"breadth": .35, "momentum": .30, "volume_pressure": .20, "vwap_signal": .15}


def normalize(x, scale):
    return np.tanh(x / scale).clip(-1, 1)


def compute(qqq: pd.DataFrame, constituents: pd.DataFrame | None = None) -> pd.DataFrame:
    """QQQ OHLCV indexed by timestamp, optional wide matrix of constituent closes.

    Input must be chronological, timezone-aware NY regular session, 5-minute bars.
    Returns one score per complete bar. No look-ahead, and all rolling features reset daily.
    """
    q = qqq.copy().sort_index()
    q.columns = [str(c).lower() for c in q.columns]
    required = {'open','high','low','close','volume'}
    if not required.issubset(q.columns):
        raise ValueError(f"Missing QQQ columns: {sorted(required-set(q.columns))}")
    if not isinstance(q.index, pd.DatetimeIndex) or q.index.tz is None:
        raise ValueError('Timestamps must be timezone-aware (America/New_York).')
    if q.index.has_duplicates:
        raise ValueError('Duplicate timestamps')
    if (q['volume'] < 0).any() or (q['close'] <= 0).any():
        raise ValueError('Invalid price/volume')
    q = q.between_time('09:35','16:00').copy()  # end-of-bar timestamps
    dates = pd.Series(q.index.tz_convert('America/New_York').date, index=q.index)
    out = []
    for _, d in q.groupby(dates, sort=True):
        d = d.copy()
        if d.empty: continue
        ret5 = d['close'].pct_change()
        ret15 = d['close'].pct_change(3)
        # Prior rolling realized volatility, with minimum floor; no future data.
        vol5 = ret5.shift(1).rolling(12, min_periods=6).std().clip(lower=.0003)
        mom = normalize(.4*ret5/vol5 + .6*ret15/(vol5*np.sqrt(3)), 1.8)
        rng = d['high']-d['low']
        location = ((2*d['close']-d['high']-d['low'])/rng.replace(0,np.nan)).fillna(0).clip(-1,1)
        pressure = (location*d['volume']).rolling(5, min_periods=3).sum()/d['volume'].rolling(5, min_periods=3).sum().replace(0,np.nan)
        typical = (d['high']+d['low']+d['close'])/3
        vwap = (typical*d['volume']).cumsum()/d['volume'].cumsum().replace(0,np.nan)
        vwap_signal = normalize((d['close']/vwap-1)/vol5, 1.5)
        if constituents is not None and not constituents.empty:
            c = constituents.reindex(d.index).ffill(limit=1)
            # Require 15-min history, and at least 20 valid constituent observations.
            r = c.pct_change(3, fill_method=None)
            valid = r.notna().sum(axis=1)
            breadth = (2*(r.gt(0).sum(axis=1)/valid.replace(0,np.nan))-1).where(valid >= 20)
            source = 'constituents'
        else:
            # Proxy is explicitly marked; NOT genuine Nasdaq-100 breadth.
            breadth = normalize(ret15/ (vol5*np.sqrt(3)), 1.8)
            source = 'QQQ proxy (no constituent breadth)'
        d['breadth'] = breadth
        d['momentum'] = mom
        d['volume_pressure'] = pressure
        d['vwap_signal'] = vwap_signal
        d['breadth_source'] = source
        features = d[list(WEIGHTS)]
        d['MER'] = (50 + 50*sum(features[k]*v for k,v in WEIGHTS.items())).where(features.notna().all(axis=1))
        d['velocity_15m'] = d['MER'] - d['MER'].shift(3)
        d['acceleration_15m'] = d['velocity_15m'] - d['velocity_15m'].shift(3)
        prev = d['MER'].shift(1)
        fear = prev.rolling(3,min_periods=3).min() < 40
        greed = prev.rolling(3,min_periods=3).max() > 60
        bullish = fear & (d['velocity_15m'] >= 12) & (d['breadth'] > 0)
        bearish = greed & (d['velocity_15m'] <= -12) & (d['breadth'] < 0)
        d['signal'] = np.select([bullish,bearish],['bullish_reversal','bearish_reversal'],default='neutral')
        out.append(d)
    return pd.concat(out) if out else q.assign(MER=np.nan)


def evaluate(result: pd.DataFrame, horizons=(3,6,12,24)) -> pd.DataFrame:
    """Exploratory forward QQQ returns after signals; excludes session boundary."""
    rows=[]
    for h in horizons:
        fwd = result.groupby(result.index.tz_convert('America/New_York').date)['close'].transform(lambda x: x.shift(-h)/x-1)
        for signal in ['bullish_reversal','bearish_reversal']:
            selected = fwd[result['signal'].eq(signal)].dropna()
            direction = 1 if signal.startswith('bullish') else -1
            rows.append({'signal':signal,'horizon_minutes':h*5,'observations':len(selected),
                         'directional_hit_rate':float((direction*selected>0).mean()) if len(selected) else np.nan,
                         'mean_signed_return_pct':float((direction*selected).mean()*100) if len(selected) else np.nan})
    return pd.DataFrame(rows)
