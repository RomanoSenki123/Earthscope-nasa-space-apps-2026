# Data and methods

## Source

| Item | Value |
|---|---|
| Service | NASA POWER Monthly and Annual API |
| Endpoint | `https://power.larc.nasa.gov/api/temporal/monthly/point` |
| Documentation | <https://power.larc.nasa.gov/docs/services/api/temporal/monthly/> |
| Underlying product | NASA GMAO MERRA-2 reanalysis (as reported in the response `header.sources`) |
| Community | `SB` |
| Format | JSON |
| API version observed | v2.10.0 |
| First accessed for this project | 14 November 2026 |

Example request (Bridgetown, 1991–2025):

```text
https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=T2M&community=SB&latitude=13.0975&longitude=-59.6167&start=1991&end=2025&format=JSON
```

The app shows the exact request URL and retrieval time for every series in its
**Data provenance** panel, and writes both into the summary CSV.

## Parameters

| Key | NASA long name | Units returned | Shown as | Verified |
|---|---|---|---|---|
| `T2M` | Temperature at 2 Meters | `C` | °C | Yes, 14 Nov 2026 |
| `RH2M` | Relative Humidity at 2 Meters | `%` | % (trends in percentage points) | Yes, 14 Nov 2026 |

## Locations

Approximate city reference points used to select a model grid cell. They are not
weather stations. London is included only as a reference point outside the
Caribbean. Users can also enter any latitude and longitude (rounded to four
decimal places); the same processing applies.

| Place | Latitude | Longitude |
|---|---:|---:|
| Bridgetown, Barbados | 13.0975 | −59.6167 |
| Kingston, Jamaica | 17.9712 | −76.7936 |
| Georgetown, Guyana | 6.8013 | −58.1551 |
| Port of Spain, Trinidad and Tobago | 10.6549 | −61.5019 |
| London, United Kingdom | 51.5074 | −0.1278 |

## Response handling

The series is read from `properties.parameter.<KEY>`, a mapping of `YYYYMM` keys
to numbers. Observed in real responses: each year also has a `YYYY13` key holding
NASA's own annual value. EarthScope skips it and recomputes annual means itself so
that incomplete years can be detected.

A record is removed, and listed in the provenance panel, when:

- the key is not six digits, or the month is not 01–12;
- the year is outside the requested range;
- the value is not a number, or is NaN or infinite;
- the value equals the fill value from `header.fill_value` (−999);
- the value is physically impossible (`T2M` outside −90 to 60 °C, `RH2M` outside 0 to 100 %).

Nothing is forward-filled, interpolated or estimated. Requests use a 30-second
timeout and retry up to twice on HTTP 429, 5xx or network errors. Other errors are
reported to the user. Successful results are cached for 24 hours.

## Annual mean

The annual mean is the arithmetic mean of the 12 monthly means, computed only for
years with all 12 valid months. Years that fall short are excluded and listed in
the app. The selectable range ends at the last fully completed calendar year, so
the current partial year is never included.

This unweighted mean of months differs very slightly from a day-weighted mean. As
a check on 14 November 2026, EarthScope's annual means were compared with NASA's
own annual values (the `YYYY13` entries) for the five presets over 1991–2025: the
largest difference in any year was 0.015 °C at the Caribbean points and 0.058 °C
at London, and the trend per decade agreed to within 0.001 °C. It
suits mean-state variables like temperature and humidity and should not be reused
for totals such as precipitation.

## Trend

`scipy.stats.linregress(year, annual_mean)` on at least 10 complete years.

| Quantity | Definition |
|---|---|
| Slope per decade | slope per year × 10 |
| 95% confidence interval | slope ± t(0.975, n − 2) × standard error |
| p-value | two-sided test that the slope is zero |
| R² | squared correlation coefficient |
| Significant | p < 0.05 |

If there are fewer than 10 complete years, or every value is identical, or the
fit is not finite, the app reports "Insufficient data for trend inference" and
shows no p-value. The fitted line is drawn only across observed years.

As a diagnostic, the app also reports the lag-1 autocorrelation of the residuals
(using consecutive years only). It is not used to adjust the results.

## Robust cross-check

The same annual series is analyzed a second way:

| Quantity | Definition |
|---|---|
| Theil–Sen slope | median of the slopes between every pair of years (`scipy.stats.theilslopes`), with its 95% confidence interval |
| Mann–Kendall test | test for a monotonic trend, computed as Kendall's tau between year and annual mean (`scipy.stats.kendalltau`) |

These methods do not assume a straight line or normally distributed errors, and a
few unusual years affect them much less. Like least squares, they assume the years
are independent, so serial correlation can still make their p-values optimistic.
The app states whether the two methods agree on direction and on significance.

Results on 14 November 2026 for `T2M`, 1991–2025:

| Location | Least squares (°C/decade) | Theil–Sen (°C/decade) | Mann–Kendall p |
|---|---:|---:|---:|
| Bridgetown, Barbados | +0.315 | +0.308 | < 0.001 |
| Kingston, Jamaica | +0.220 | +0.200 | < 0.001 |
| Georgetown, Guyana | +0.258 | +0.239 | < 0.001 |
| Port of Spain, Trinidad and Tobago | +0.090 | +0.073 | 0.217 |
| London, United Kingdom | +0.365 | +0.393 | < 0.001 |

## Plain-language explanations

The "Explain this result" panel offers wording for a student, the general public
or a scientist. The text is produced from fixed templates filled with the computed
numbers. No AI model is called by the app.

## Verification performed (14 November 2026)

- All five presets returned 420 of 420 monthly `T2M` values for 1991–2025 with no fill values and no filtered records; units were reported as `C` and the source as MERRA2.
- The regression output is tested against closed-form least-squares formulas computed independently of `linregress` (slope, intercept, standard error, p-value, R², confidence interval).
- The annual means were compared with NASA's own annual values, as described above.

## Limitations

- Each result describes one sampled grid cell. A few cells cannot establish a Caribbean-wide rate, and comparing with one city elsewhere does not show how the region compares with the world.

- Reanalysis values represent a grid cell (about 0.5° × 0.625° for MERRA-2), not a station. Coastal and island cells mix land and sea.
- Ordinary least squares assumes independent residuals. For the default Bridgetown and Kingston temperature series the lag-1 residual autocorrelation was about 0.37–0.38 on 14 November 2026, so the reported intervals and p-values are somewhat optimistic.
- A linear model does not capture steps, cycles (such as ENSO) or acceleration.
- Slopes depend on the start and end years.
- Reanalysis products can contain artificial shifts when the observing system changes.
- Point comparisons are not national comparisons. A trend is not an attribution of cause.
