# EarthScope — Earth System Trend Detective

A NASA Space Apps Challenge 2026 project by team **Bajan Chief** for the challenge
[Be An Earth System Trend Detective!](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/)

EarthScope is a small Streamlit app that downloads historical NASA POWER data for a
chosen place and answers four questions in plain language:

- **What** is changing? (2-meter air temperature or relative humidity)
- **Where**? (a Caribbean preset or any latitude/longitude, optionally compared with a second place)
- **How much**? (linear trend per decade with a 95% confidence interval)
- **Is it statistically significant?** (p-value, R², and an honest explanation)

EarthScope focuses on the Caribbean, where the team is based. Every result is a
model-derived estimate for one sampled grid cell. It is not a national,
Caribbean-wide or global average.

EarthScope is not a NASA product and is not endorsed by NASA.

## Run it

Requires Python 3.11 or newer and an internet connection (no API key or account).

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python` instead.

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## What it does

| Feature | Status |
|---|---|
| Live NASA POWER monthly data (`T2M`, `RH2M`) | Implemented |
| Four Caribbean presets: Bridgetown, Kingston, Georgetown, Port of Spain | Implemented |
| One reference preset outside the region: London | Implemented |
| Custom latitude/longitude anywhere in the world | Implemented |
| Year-range selection, 1981 to the last complete year (default 1991–2025) | Implemented |
| Removal of fill values and invalid records, with disclosure | Implemented |
| Annual means from complete 12-month years only; excluded years listed | Implemented |
| Linear trend: slope per decade, 95% CI, p-value, R², sample size | Implemented |
| Interactive chart of annual means with fitted trend line | Implemented |
| Two-location comparison chart and table | Implemented |
| Annual-data CSV and trend-summary CSV downloads | Implemented |
| Provenance, method, limitations and AI-assistance panels | Implemented |
| Map, file upload, public deployment | Not implemented (see [docs/FUTURE_WORK.md](docs/FUTURE_WORK.md)) |

## Example result

Computed by the app from NASA POWER data retrieved on 14 November 2026
(API v2.10.0), for 1991–2025, 35 complete years at each location:

| Location | Trend (°C/decade) | 95% CI (°C/decade) | p-value | R² |
|---|---:|---:|---:|---:|
| Bridgetown, Barbados | +0.315 | +0.215 to +0.415 | < 0.001 | 0.55 |
| Kingston, Jamaica | +0.220 | +0.134 to +0.305 | < 0.001 | 0.45 |

These are grid-cell values from a reanalysis model, not station measurements, and
the numbers may shift slightly if NASA reprocesses its data. Run the app to
reproduce them.

## Deploying (optional)

The app needs no secrets, database or API key, so it can run on Streamlit
Community Cloud as it is:

1. Push this repository to GitHub and make it public.
2. At <https://share.streamlit.io>, sign in with GitHub and choose **Create app**.
3. Select the repository, branch `main`, and main file `app.py`. Under advanced settings pick Python 3.11 or newer.
4. Deploy, then open the URL in a private browser window and confirm that the default Bridgetown view loads real data.

No live URL exists yet. Add it here only after it has been verified.

## Data source

- **NASA POWER Monthly and Annual API** — <https://power.larc.nasa.gov/docs/services/api/temporal/monthly/>
- Endpoint: `https://power.larc.nasa.gov/api/temporal/monthly/point` with `community=SB`
- Meteorological values originate from NASA GMAO's **MERRA-2** reanalysis.
- Parameters: `T2M` (Temperature at 2 Meters, °C) and `RH2M` (Relative Humidity at 2 Meters, %).

Suggested acknowledgment: *These data were obtained from the NASA Langley Research
Center (LaRC) POWER Project funded through the NASA Earth Science/Applied Science
Program.*

## Method in brief

1. Request monthly values for the selected point and years.
2. Drop NASA's fill value (−999), non-numeric values and physically impossible values. Nothing is interpolated.
3. Average the 12 monthly means into an annual mean, only for years with all 12 months.
4. Fit `annual mean = intercept + slope × year` with `scipy.stats.linregress` (at least 10 complete years).
5. Report slope × 10 per decade, the 95% interval `slope ± t(0.975, n−2) × SE`, the p-value and R².

Full details: [docs/DATA_METHODS.md](docs/DATA_METHODS.md).

## Limitations

- Values are model-derived (reanalysis) for a grid cell roughly 50 km across, not thermometer readings at the chosen point.
- A straight line can miss non-linear change; serial correlation between years can make p-values and intervals look more certain than they are.
- The chosen years affect the slope. Two points are not two countries, and one city outside the Caribbean is not a global benchmark.
- Significance is not importance, a trend is not a cause, and "not significant" does not mean "no change".
- The app describes history only. It makes no forecasts.

## Project layout

```text
app.py                  Streamlit interface
earthscope/config.py    locations, variables, API settings
earthscope/nasa_power.py  request, validation and parsing
earthscope/processing.py  annual aggregation
earthscope/statistics.py  linear trend and uncertainty
earthscope/charts.py    Plotly figure
earthscope/explanations.py  plain-language wording
tests/                  unit tests (synthetic fixtures only)
docs/                   methods, AI disclosure, future work
submission/             draft NASA Space Apps submission text
```

## AI assistance

Claude Code (Anthropic) assisted with implementation, tests and documentation.
See [docs/AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md).

## License

MIT — see [LICENSE](LICENSE). NASA data are subject to NASA's own data policies.
