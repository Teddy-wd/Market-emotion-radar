# Market Emotion Radar — Nasdaq 100 (v0.2)

Streamlit dashboard with automatic 5-minute refresh, Yahoo Finance QQQ intraday bars, optional breadth from an **unweighted sample of up to 29 Nasdaq-100-related large-cap stocks**, and CSV input. The score is a heuristic price/volume pressure index, not measured investor emotion or a validated prediction.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy publicly with Streamlit Community Cloud

1. Create a GitHub repository and upload the **contents** of this directory (including `app.py`, `engine.py`, `live_data.py`, `requirements.txt`, `.streamlit/config.toml`).
2. Visit https://share.streamlit.io/ and sign in with GitHub.
3. Select **Create app**, choose your repository and branch, set entrypoint to `app.py`, and deploy.
4. Open the generated `*.streamlit.app` URL.

Hosting is not included in this ZIP. Yahoo Finance may throttle or block cloud hosts; this is a best-effort source, not a guaranteed live service. The data may be delayed. The UI clearly marks stale or previous-session data.

## Important limitations

- 5-minute bars are based on Yahoo timestamps shifted from bar start to bar end, and only fully elapsed bars are used.
- The sample of stocks is **not** all current Nasdaq-100 constituents, and does not use historical membership or index weights.
- On provider failure, breadth reverts to a QQQ proxy, explicitly labeled.
- Regular US session only, with no holiday/early-close calendar.
- MER weights and reversal thresholds are experimental; no walk-forward validation or calibrated reversal probabilities.
- No trading automation, orders, or investment advice.

## Tests

```bash
pytest -q
```

## v0.3 — Dominance Shift Detector

`dominance.py` adds a *causal* 5-minute detector. A LONG signal requires MER crossing above 53, MER increasing by >=8 points over 10 minutes, breadth >=+0.10, QQQ closing above the previous 3 bars' high, and current volume >=0.75x the median of the previous 4–6 bars. SHORT is symmetric with MER crossing below 47. A 15-minute cooldown limits repeat signals. TRANSITION is only an observation; it is **not** a confirmed entry. These thresholds are experimental and adjustable.

The event study simulates entry at the **next bar's open**, exits at the close of the +5/+10/+15/+30 minute bar, excludes session-crossing outcomes, and subtracts an adjustable round-trip cost (3 bps default). It does **not** account for all execution frictions or overlapping-signal dependence.

### Methodology for serious validation

1. Collect 6–24 months of clean, licensed 5-minute QQQ OHLCV and *point-in-time* Nasdaq-100 constituents; Yahoo's 7-day intraday window is only for smoke tests, not robust backtesting.
2. Use session-aware timestamps in New York; account for holidays, early closes, missing bars, and delayed quotes. Never use incomplete bars.
3. Freeze parameters on an initial training window, then evaluate on chronologically subsequent weeks; roll forward without tuning on test data.
4. Compare against a simple VWAP breakout, a 15-minute momentum rule, and random time-matched entry baselines. Keep identical transaction-cost assumptions.
5. Report signal count, net hit rate, average/median net bps, drawdown, adverse/favorable excursion, confidence intervals clustered by session, and sensitivity to 1–10 bps additional slippage.
6. Separate LONG/SHORT, morning/afternoon, high/low volatility, and different market regimes. Require enough independent sessions; do not claim success from a handful of observations.
7. Paper trade for several weeks with *live timestamps* and recorded actual latency before considering real money. Do not infer actual tradability from a Yahoo-delayed score.

### Installation

```bash
pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

### Deploy to Streamlit

Upload `dominance.py`, updated `app.py`, `README.md`, and `tests/test_dominance.py` to the existing GitHub repository; Streamlit Cloud redeploys automatically. Ensure `dominance.py` is at the repository root next to `app.py`.
