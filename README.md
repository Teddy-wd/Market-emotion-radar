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
