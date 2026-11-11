"""Causal 5-minute dominance detector and event study."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class ShiftConfig:
    threshold: float = 8.0
    bullish_level: float = 53.0
    bearish_level: float = 47.0
    min_breadth: float = .10
    min_relative_volume: float = .75
    cooldown_bars: int = 3
    price_lookback: int = 3


def detect(result: pd.DataFrame, cfg: ShiftConfig = ShiftConfig(),
           timezone='America/New_York') -> pd.DataFrame:
    required={'MER','breadth','close','high','low','volume'}
    if not required.issubset(result.columns):
        raise ValueError(f'Colonnes manquantes : {sorted(required-set(result.columns))}')
    if not isinstance(result.index,pd.DatetimeIndex) or result.index.tz is None:
        raise ValueError('Index horodaté avec fuseau horaire requis.')
    if result.index.has_duplicates or not result.index.is_monotonic_increasing:
        raise ValueError('Horodatages dupliqués ou non triés.')
    chunks=[]
    for _,d in result.groupby(result.index.tz_convert(timezone).date):
        d=d.copy()
        mer=d.MER
        d['delta_10m']=mer.diff(2)
        reference=d.volume.shift(1).rolling(6,min_periods=4).median()
        d['rvol']=(d.volume/reference.replace(0,np.nan)).replace([np.inf,-np.inf],np.nan)
        prev_high=d.high.shift(1).rolling(cfg.price_lookback,min_periods=cfg.price_lookback).max()
        prev_low=d.low.shift(1).rolling(cfg.price_lookback,min_periods=cfg.price_lookback).min()
        up=(mer.shift(1).le(cfg.bullish_level) & mer.gt(cfg.bullish_level) &
            d.delta_10m.ge(cfg.threshold) & d.breadth.ge(cfg.min_breadth) &
            d.close.gt(prev_high) & d.rvol.ge(cfg.min_relative_volume))
        down=(mer.shift(1).ge(cfg.bearish_level) & mer.lt(cfg.bearish_level) &
              d.delta_10m.le(-cfg.threshold) & d.breadth.le(-cfg.min_breadth) &
              d.close.lt(prev_low) & d.rvol.ge(cfg.min_relative_volume))
        state=np.full(len(d),'NO EDGE',dtype=object)
        state[np.asarray((d.delta_10m.ge(cfg.threshold)&d.breadth.gt(0)).fillna(False))]='TRANSITION HAUSSIÈRE'
        state[np.asarray((d.delta_10m.le(-cfg.threshold)&d.breadth.lt(0)).fillna(False))]='TRANSITION BAISSIÈRE'
        signals=np.full(len(d),'none',dtype=object)
        last_event=-cfg.cooldown_bars-1
        for i in range(len(d)):
            if i-last_event<=cfg.cooldown_bars: continue
            if bool(up.iloc[i]):
                signals[i]='LONG';state[i]='BUYERS TAKING CONTROL';last_event=i
            elif bool(down.iloc[i]):
                signals[i]='SHORT';state[i]='SELLERS TAKING CONTROL';last_event=i
        d['shift_state']=state
        d['shift_signal']=signals
        chunks.append(d)
    return pd.concat(chunks) if chunks else result.assign(shift_state='NO EDGE',shift_signal='none',delta_10m=np.nan,rvol=np.nan)


def event_study(df: pd.DataFrame, horizons=(1,2,3,6),cost_bps=3.0,
                timezone='America/New_York'):
    if not {'shift_signal','open','close'}.issubset(df.columns):
        raise ValueError('Colonnes requises absentes pour le backtest.')
    events=[]
    for date,day in df.groupby(df.index.tz_convert(timezone).date):
        day=day.sort_index()
        for i in range(len(day)):
            side=day.shift_signal.iloc[i]
            if side not in ('LONG','SHORT') or i+1>=len(day):continue
            entry=day.open.iloc[i+1]
            if not np.isfinite(entry) or entry<=0:continue
            direction=1 if side=='LONG' else -1
            for h in horizons:
                j=i+h
                if j>=len(day):continue
                exit_price=day.close.iloc[j]
                if not np.isfinite(exit_price):continue
                gross=direction*(exit_price/entry-1)*10000
                events.append({'date':str(date),'signal_time':day.index[i],'side':side,
                               'entry_time':day.index[i+1],'horizon_minutes':5*h,
                               'entry_price':float(entry),'exit_price':float(exit_price),
                               'gross_bps':float(gross),'net_bps':float(gross-cost_bps)})
    details=pd.DataFrame(events)
    rows=[]
    for side in ('LONG','SHORT'):
        for h in horizons:
            sub=details[(details.side==side)&(details.horizon_minutes==h*5)] if not details.empty else pd.DataFrame()
            vals=sub.net_bps if not sub.empty else pd.Series(dtype=float)
            rows.append({'side':side,'horizon_minutes':5*h,'observations':len(vals),
                         'hit_rate_net':float((vals>0).mean()) if len(vals) else np.nan,
                         'mean_net_bps':float(vals.mean()) if len(vals) else np.nan,
                         'median_net_bps':float(vals.median()) if len(vals) else np.nan})
    return pd.DataFrame(rows),details
