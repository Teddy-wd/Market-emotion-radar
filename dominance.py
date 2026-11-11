"""Causal, 5-minute dominance shift detector and exploratory event study.

All signals are determined at the close of a completed bar. A hypothetical
execution is at the *next* bar's open; no intrabar entry is assumed.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

NY = 'America/New_York'

@dataclass(frozen=True)
class ShiftConfig:
    threshold: float = 8.0       # MER change over 10 minutes
    bullish_level: float = 53.0  # hysteresis avoids oscillations around 50
    bearish_level: float = 47.0
    min_breadth: float = 0.10
    min_relative_volume: float = 0.75
    cooldown_bars: int = 3       # 15 minutes
    price_lookback: int = 3      # prior 15-min high/low
    max_age_minutes: int = 20


def detect(result: pd.DataFrame, cfg: ShiftConfig = ShiftConfig()) -> pd.DataFrame:
    """Return result with shift_state, shift_signal, rvol, and reasons.

    Relative volume is compared with preceding bars of the SAME session.
    No future bars are used, and no events are emitted during warm-up.
    """
    required = {'MER', 'breadth', 'close', 'high', 'low', 'volume'}
    missing = required - set(result.columns)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')
    if not isinstance(result.index, pd.DatetimeIndex) or result.index.tz is None:
        raise ValueError('Timezone-aware timestamp index required')
    if result.index.has_duplicates:
        raise ValueError('Duplicate timestamps')
    if not result.index.is_monotonic_increasing:
        raise ValueError('Timestamps must be sorted')
    chunks = []
    for _, d in result.groupby(result.index.tz_convert(NY).date, sort=True):
        d = d.copy()
        mer = d['MER']
        d['delta_10m'] = mer.diff(2)
        # Prior 6 bars = 30 minutes, excludes current bar; never crosses session.
        reference = d['volume'].shift(1).rolling(6, min_periods=4).median()
        d['rvol'] = (d['volume'] / reference.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        prev_high = d['high'].shift(1).rolling(cfg.price_lookback, min_periods=cfg.price_lookback).max()
        prev_low = d['low'].shift(1).rolling(cfg.price_lookback, min_periods=cfg.price_lookback).min()
        prior = mer.shift(1)
        # A crossing of a hysteresis boundary, OR an accelerated push across it.
        up_cross = (prior <= cfg.bullish_level) & (mer > cfg.bullish_level)
        down_cross = (prior >= cfg.bearish_level) & (mer < cfg.bearish_level)
        up = (up_cross & (d['delta_10m'] >= cfg.threshold) &
              (d['breadth'] >= cfg.min_breadth) & (d['close'] > prev_high) &
              (d['rvol'] >= cfg.min_relative_volume))
        down = (down_cross & (d['delta_10m'] <= -cfg.threshold) &
                (d['breadth'] <= -cfg.min_breadth) & (d['close'] < prev_low) &
                (d['rvol'] >= cfg.min_relative_volume))
        # 'Transition' is an observation, not a tradable event.
        transition_up = (d['delta_10m'] >= cfg.threshold) & (d['breadth'] > 0)
        transition_down = (d['delta_10m'] <= -cfg.threshold) & (d['breadth'] < 0)
        state = np.full(len(d), 'NO EDGE', dtype=object)
        state[np.asarray(transition_up.fillna(False))] = 'TRANSITION HAUSSIÈRE'
        state[np.asarray(transition_down.fillna(False))] = 'TRANSITION BAISSIÈRE'
        signals = np.full(len(d), 'none', dtype=object)
        last_event = -cfg.cooldown_bars - 1
        for i in range(len(d)):
            if i - last_event <= cfg.cooldown_bars:
                continue
            if bool(up.iloc[i]):
                signals[i] = 'LONG'; state[i] = 'BUYERS TAKING CONTROL'; last_event = i
            elif bool(down.iloc[i]):
                signals[i] = 'SHORT'; state[i] = 'SELLERS TAKING CONTROL'; last_event = i
        d['shift_state'] = state
        d['shift_signal'] = signals
        chunks.append(d)
    return pd.concat(chunks) if chunks else result.assign(shift_state='NO EDGE', shift_signal='none')


def event_study(df: pd.DataFrame, horizons=(1, 2, 3, 6), cost_bps=3.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate signals with next-bar-open entry and same-session future close.

    A 3 bps round-trip cost is an illustrative default, NOT a broker quote.
    Results with no next open or insufficient horizon are excluded.
    Overlapping events are NOT treated as independent observations.
    """
    required = {'shift_signal', 'open', 'close'}
    if not required.issubset(df.columns):
        raise ValueError('Missing required columns for evaluation')
    events = []
    for date, day in df.groupby(df.index.tz_convert(NY).date):
        day = day.sort_index()
        for i in range(len(day)):
            side = day['shift_signal'].iloc[i]
            if side not in ('LONG', 'SHORT') or i+1 >= len(day):
                continue
            entry = day['open'].iloc[i+1]
            if not np.isfinite(entry) or entry <= 0:
                continue
            direction = 1 if side == 'LONG' else -1
            for h in horizons:
                # Signal at close of bar i, entry at next bar OPEN i+1.
                # Exit at close of bar i+h; h=1 => close of entry bar.
                j = i+h
                if j >= len(day):
                    continue
                exit_price = day['close'].iloc[j]
                if not np.isfinite(exit_price):
                    continue
                gross = direction*(exit_price/entry-1)*10000
                events.append({'date':str(date), 'signal_time':day.index[i], 'side':side,
                               'entry_time':day.index[i+1], 'horizon_minutes':5*h,
                               'entry_price':float(entry), 'exit_price':float(exit_price),
                               'gross_bps':float(gross), 'net_bps':float(gross-cost_bps)})
    details = pd.DataFrame(events)
    rows = []
    for side in ('LONG','SHORT'):
        for h in horizons:
            subset = details[(details.side == side) & (details.horizon_minutes == h*5)] if not details.empty else pd.DataFrame()
            vals = subset['net_bps'] if not subset.empty else pd.Series(dtype=float)
            rows.append({'side':side, 'horizon_minutes':5*h, 'observations':len(vals),
                         'hit_rate_net':float((vals>0).mean()) if len(vals) else np.nan,
                         'mean_net_bps':float(vals.mean()) if len(vals) else np.nan,
                         'median_net_bps':float(vals.median()) if len(vals) else np.nan})
    return pd.DataFrame(rows), details
