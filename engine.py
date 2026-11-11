"""Causal 5-minute Market Emotion Radar; market-aware sessions."""
import numpy as np
import pandas as pd
from markets import Market, NASDAQ

WEIGHTS = {'breadth': .35, 'momentum': .30, 'volume_pressure': .20, 'vwap_signal': .15}


def normalize(x, scale):
    return np.tanh(x / scale).clip(-1, 1)


def compute(price: pd.DataFrame, constituents: pd.DataFrame | None = None,
            market: Market = NASDAQ) -> pd.DataFrame:
    q = price.copy().sort_index()
    q.columns = [str(c).lower() for c in q.columns]
    required = {'open','high','low','close','volume'}
    if not required.issubset(q.columns):
        raise ValueError(f'Colonnes manquantes : {sorted(required-set(q.columns))}')
    if not isinstance(q.index, pd.DatetimeIndex) or q.index.tz is None:
        raise ValueError('Index horodaté avec fuseau horaire requis.')
    if q.index.has_duplicates:
        raise ValueError('Horodatages dupliqués.')
    if (q['volume'] < 0).any() or (q['close'] <= 0).any():
        raise ValueError('Prix ou volumes invalides.')
    q = q.tz_convert(market.timezone).between_time(market.start, market.end)
    chunks = []
    for _, d in q.groupby(q.index.date):
        d = d.copy()
        ret5 = d.close.pct_change()
        ret15 = d.close.pct_change(3)
        vol5 = ret5.shift(1).rolling(12, min_periods=6).std().clip(lower=.0003)
        d['momentum'] = normalize(.4*ret5/vol5 + .6*ret15/(vol5*np.sqrt(3)), 1.8)
        rng = d.high-d.low
        location = ((2*d.close-d.high-d.low)/rng.replace(0,np.nan)).fillna(0).clip(-1,1)
        d['volume_pressure'] = (location*d.volume).rolling(5,min_periods=3).sum()/d.volume.rolling(5,min_periods=3).sum().replace(0,np.nan)
        typical = (d.high+d.low+d.close)/3
        vwap = (typical*d.volume).cumsum()/d.volume.cumsum().replace(0,np.nan)
        d['vwap_signal'] = normalize((d.close/vwap-1)/vol5,1.5)
        if constituents is not None and not constituents.empty:
            c = constituents.tz_convert(market.timezone).reindex(d.index).ffill(limit=1)
            r = c.pct_change(3, fill_method=None)
            valid = r.notna().sum(axis=1)
            d['breadth'] = (2*r.gt(0).sum(axis=1)/valid.replace(0,np.nan)-1).where(valid >= market.min_breadth_count)
            d['breadth_source'] = 'échantillon de constituants'
        else:
            d['breadth'] = normalize(ret15/(vol5*np.sqrt(3)),1.8)
            d['breadth_source'] = 'proxy ETF (non indépendant)'
        features = d[list(WEIGHTS)]
        d['MER'] = (50+50*sum(features[k]*w for k,w in WEIGHTS.items())).where(features.notna().all(axis=1))
        d['velocity_15m'] = d.MER-d.MER.shift(3)
        d['acceleration_15m'] = d.velocity_15m-d.velocity_15m.shift(3)
        prev = d.MER.shift(1)
        fear = prev.rolling(3,min_periods=3).min()<40
        greed = prev.rolling(3,min_periods=3).max()>60
        d['signal'] = np.select([fear & (d.velocity_15m>=12) & (d.breadth>0),
                                 greed & (d.velocity_15m<=-12) & (d.breadth<0)],
                                ['bullish_reversal','bearish_reversal'],default='neutral')
        chunks.append(d)
    return pd.concat(chunks) if chunks else q.assign(MER=np.nan)


def evaluate(result, horizons=(3,6,12,24), timezone='America/New_York'):
    rows=[]
    for h in horizons:
        fwd=result.groupby(result.index.tz_convert(timezone).date)['close'].transform(lambda x:x.shift(-h)/x-1)
        for signal in ['bullish_reversal','bearish_reversal']:
            selected=fwd[result.signal.eq(signal)].dropna()
            direction=1 if signal.startswith('bullish') else -1
            rows.append({'signal':signal,'horizon_minutes':h*5,'observations':len(selected),
                         'directional_hit_rate':float((direction*selected>0).mean()) if len(selected) else np.nan,
                         'mean_signed_return_pct':float((direction*selected).mean()*100) if len(selected) else np.nan})
    return pd.DataFrame(rows)
