# Project summary (draft)

**Title:** EarthScope — Earth System Trend Detective
**Team:** Bajan Chief
**Challenge:** Be An Earth System Trend Detective!

## Short summary

EarthScope is an interactive Python app that turns NASA POWER Earth-system data
into a clear answer about change over time. It focuses on the Caribbean: a user picks a preset Caribbean location or enters
any latitude and longitude, a
variable (2-meter air temperature or relative humidity) and a range of years.
EarthScope downloads the monthly record from NASA, builds annual means from
complete years only, fits a linear trend, and reports how fast the variable is
changing, the 95% confidence interval, and whether the trend is statistically
significant, in plain language. Two locations can be compared side by side, and
the processed data and trend summary can be downloaded as CSV. The app shows where
every number came from and explains what the statistics do and do not mean. Each
result is a model-derived estimate for one grid cell, not a regional average.

## One-line version

Pick a place and a variable; EarthScope shows what NASA data say has changed, how
fast, and whether the trend is statistically significant.
