"""Stage 12: descriptive daily rainy-versus-dry ridership analysis."""
from __future__ import annotations

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "DataProcessed"
SOURCE = DATA / "metro_weather_hourly_merged.csv"
OUT_DAILY = DATA / "stage12_daily_rainfall_ridership.csv"
OUT_STATS = DATA / "stage12_daily_rainfall_ridership_results.csv"
OUT_REPORT = DATA / "stage12_daily_rainfall_ridership_report.md"
OUT_GROUP = DATA / "stage12_daily_rainfall_group_comparison.png"
OUT_ASSOC = DATA / "stage12_daily_rainfall_association.png"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def need(condition, message):
    if not condition:
        raise RuntimeError(message)

def main():
    outputs = [OUT_DAILY, OUT_STATS, OUT_REPORT, OUT_GROUP, OUT_ASSOC]
    need(not [p for p in outputs if p.exists()], "Refusing to overwrite Stage 12 outputs: " + ", ".join(str(p) for p in outputs if p.exists()))
    raw = pd.read_csv(SOURCE, parse_dates=["time", "businessday"])
    required = {"time", "businessday", "direction", "ridership_count", "rain_mm"}
    need(required <= set(raw.columns), "Hourly merged source lacks required fields")
    need(raw["rain_mm"].notna().all() and (raw["rain_mm"] >= 0).all(), "Rain values are missing or negative")
    need(raw.groupby("time")["rain_mm"].nunique().le(1).all(), "Weather differs between Entry/Exit rows at an hour")

    raw["date"] = raw["time"].dt.normalize()
    weather = raw.drop_duplicates("time").groupby("date", as_index=False).agg(
        daily_rainfall_mm=("rain_mm", "sum"), weather_hours=("time", "size")
    )
    riders = raw.groupby("date", as_index=False).agg(
        total_entry_exit_ridership=("ridership_count", "sum"), ridership_rows=("ridership_count", "size")
    )
    daily = riders.merge(weather, on="date", validate="one_to_one").sort_values("date").reset_index(drop=True)
    expected_weather_hours = int(daily["weather_hours"].iloc[0])
    expected_ridership_rows = int(daily["ridership_rows"].iloc[0])
    need((daily["weather_hours"] == expected_weather_hours).all(), "Daily rainfall coverage differs across dates")
    need((daily["ridership_rows"] == expected_ridership_rows).all(), "Daily ridership coverage differs across dates")
    daily["weekday"] = pd.Categorical(daily["date"].dt.day_name(), categories=WEEKDAYS, ordered=True)
    daily["rainy"] = daily["daily_rainfall_mm"] > 0
    daily["rain_class"] = np.where(daily["rainy"], "Rainy (>0 mm)", "Dry (0 mm)")
    dry, rainy = daily.loc[~daily.rainy, "total_entry_exit_ridership"], daily.loc[daily.rainy, "total_entry_exit_ridership"]
    need(len(dry) >= 2 and len(rainy) >= 2, "Insufficient rainy or dry days for comparison")

    mean_dry, mean_rainy = float(dry.mean()), float(rainy.mean())
    diff, pct = mean_rainy - mean_dry, (mean_rainy - mean_dry) / mean_dry * 100
    welch = stats.ttest_ind(rainy, dry, equal_var=False)
    mann = stats.mannwhitneyu(rainy, dry, alternative="two-sided")
    pooled_sd = math.sqrt(((len(rainy)-1)*rainy.var(ddof=1) + (len(dry)-1)*dry.var(ddof=1)) / (len(rainy)+len(dry)-2))
    cohen_d = diff / pooled_sd
    pearson = stats.pearsonr(daily["daily_rainfall_mm"], daily["total_entry_exit_ridership"])
    spearman = stats.spearmanr(daily["daily_rainfall_mm"], daily["total_entry_exit_ridership"])

    weekday_rows = []
    for weekday in WEEKDAYS:
        part = daily[daily.weekday == weekday]
        d, r = part.loc[~part.rainy, "total_entry_exit_ridership"], part.loc[part.rainy, "total_entry_exit_ridership"]
        weekday_rows.append({"weekday": weekday, "dry_n": len(d), "rainy_n": len(r), "dry_mean": d.mean(), "rainy_mean": r.mean(), "rainy_minus_dry": r.mean()-d.mean() if len(d) and len(r) else np.nan})
    weekday = pd.DataFrame(weekday_rows)
    matched = weekday.dropna(subset=["rainy_minus_dry"])
    matched_diff = float(matched["rainy_minus_dry"].mean())
    matched_dry = float(matched["dry_mean"].mean())
    matched_pct = matched_diff / matched_dry * 100

    # OLS with weekday fixed effects gives the weekday-adjusted rainy-day difference.
    weekday_dummies = pd.get_dummies(daily["weekday"], drop_first=True, dtype=float)
    X = np.column_stack([np.ones(len(daily)), daily["rainy"].astype(float), weekday_dummies.to_numpy()])
    y = daily["total_entry_exit_ridership"].to_numpy(float)
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    df = len(y) - X.shape[1]
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X) * (resid @ resid / df)))
    weekday_t = beta[1] / se[1]
    weekday_p = 2 * stats.t.sf(abs(weekday_t), df)

    results = pd.DataFrame([
        {"analysis": "overall_rainy_vs_dry", "metric": "days", "value": len(daily), "rainy_value": len(rainy), "dry_value": len(dry)},
        {"analysis": "overall_rainy_vs_dry", "metric": "mean_daily_ridership", "value": np.nan, "rainy_value": mean_rainy, "dry_value": mean_dry},
        {"analysis": "overall_rainy_vs_dry", "metric": "rainy_minus_dry", "value": diff, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "overall_rainy_vs_dry", "metric": "percent_difference_from_dry", "value": pct, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "overall_rainy_vs_dry", "metric": "cohen_d", "value": cohen_d, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "overall_rainy_vs_dry", "metric": "welch_t_p_value", "value": welch.pvalue, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "overall_rainy_vs_dry", "metric": "mann_whitney_p_value", "value": mann.pvalue, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "weekday_matched", "metric": "equal_weekday_mean_difference", "value": matched_diff, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "weekday_matched", "metric": "equal_weekday_percent_difference", "value": matched_pct, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "weekday_adjusted_ols", "metric": "rainy_coefficient", "value": beta[1], "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "weekday_adjusted_ols", "metric": "rainy_coefficient_p_value", "value": weekday_p, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "rainfall_association", "metric": "pearson_r", "value": pearson.statistic, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "rainfall_association", "metric": "pearson_p_value", "value": pearson.pvalue, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "rainfall_association", "metric": "spearman_rho", "value": spearman.statistic, "rainy_value": np.nan, "dry_value": np.nan},
        {"analysis": "rainfall_association", "metric": "spearman_p_value", "value": spearman.pvalue, "rainy_value": np.nan, "dry_value": np.nan},
    ])
    daily.to_csv(OUT_DAILY, index=False)
    results.to_csv(OUT_STATS, index=False)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8, 5))
    groups = [dry, rainy]
    ax.boxplot(groups, tick_labels=["Dry\n(n=%d)" % len(dry), "Rainy\n(n=%d)" % len(rainy)], showfliers=False)
    rng = np.random.default_rng(42)
    for x, values, color in [(1, dry, "#5b8db8"), (2, rainy, "#4b9b67")]:
        ax.scatter(rng.normal(x, .045, len(values)), values, s=18, alpha=.6, color=color)
    ax.set_ylabel("Daily Entry + Exit ridership")
    ax.set_title("Daily ridership on dry and rainy days")
    fig.tight_layout(); fig.savefig(OUT_GROUP, dpi=180); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].scatter(daily.daily_rainfall_mm, daily.total_entry_exit_ridership, color="#3574a7", alpha=.7)
    slope, intercept = np.polyfit(daily.daily_rainfall_mm, daily.total_entry_exit_ridership, 1)
    xline = np.linspace(0, daily.daily_rainfall_mm.max(), 100)
    axes[0].plot(xline, intercept + slope*xline, color="#bb3e03")
    axes[0].set(xlabel="Daily rainfall (mm)", ylabel="Daily Entry + Exit ridership", title="Rainfall–ridership association")
    pos = np.arange(len(weekday))
    axes[1].bar(pos-.2, weekday.dry_mean, .4, label="Dry", color="#5b8db8")
    axes[1].bar(pos+.2, weekday.rainy_mean, .4, label="Rainy", color="#4b9b67")
    axes[1].set_xticks(pos, weekday.weekday, rotation=35, ha="right")
    axes[1].set(ylabel="Mean daily Entry + Exit ridership", title="Weekday-matched descriptive means")
    axes[1].legend()
    fig.tight_layout(); fig.savefig(OUT_ASSOC, dpi=180); plt.close(fig)

    report = f"""# Daily rainfall and Delhi Metro ridership

**Scope:** {daily.date.min():%Y-%m-%d} to {daily.date.max():%Y-%m-%d}; {len(daily)} calendar days. Each date has the same available coverage: {expected_weather_hours} hourly weather observations and {expected_ridership_rows} Entry/Exit ridership rows. Daily ridership is the citywide sum of all available hourly Entry and Exit counts. Daily rainfall is the sum of the existing Rajiv Chowk-aligned hourly `rain_mm` observations. A rainy day is rainfall > 0 mm over those available hours.

## Overall comparison

- Dry days: **{len(dry)}**; rainy days: **{len(rainy)}**.
- Mean daily ridership: dry **{mean_dry:,.0f}**; rainy **{mean_rainy:,.0f}**.
- Rainy minus dry: **{diff:,.0f}** ({pct:+.2f}% of the dry-day mean); Cohen's *d* = **{cohen_d:.3f}**.
- Welch two-sided t-test: *t* = {welch.statistic:.3f}, *p* = {welch.pvalue:.4g}. Mann–Whitney two-sided *p* = {mann.pvalue:.4g}.

## Weekday-matched comparison

Among the {len(matched)} weekdays with both rainy and dry observations, the equal-weekday-average rainy-minus-dry difference is **{matched_diff:,.0f}** ({matched_pct:+.2f}%). An OLS comparison controlling for weekday gives a rainy-day coefficient of **{beta[1]:,.0f}** with *p* = **{weekday_p:.4g}** (ordinary least-squares standard error).

## Rainfall–ridership association

- Pearson *r* = **{pearson.statistic:.3f}**, *p* = {pearson.pvalue:.4g}.
- Spearman rho = **{spearman.statistic:.3f}**, *p* = {spearman.pvalue:.4g}.

## Interpretation and limitations

This is an observational, unadjusted-for-calendar-and-external-events comparison except for weekday in the stated matched analysis. It does **not** establish that rainfall causes ridership changes. Rainfall is from the existing single-location weather integration and does not cover the three unrepresented overnight hours; the results may be affected by holidays, service variation, seasonality, rainfall timing/intensity, and the small number of rainy days in some weekday strata.
"""
    OUT_REPORT.write_text(report)
    print(results.to_string(index=False))
    print(f"Created {OUT_REPORT}")

if __name__ == "__main__":
    main()
