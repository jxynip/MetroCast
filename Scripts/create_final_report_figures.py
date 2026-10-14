"""Create presentation figures from existing saved Stage 1–12 data/results only."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "DataProcessed"
OUT = [
    DATA / "final_report_fig01_hourly_ridership_pattern.png",
    DATA / "final_report_fig02_station_rankings.png",
    DATA / "final_report_fig03_hourly_rainfall_distribution.png",
    DATA / "final_report_fig04_model_comparison.png",
]

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def main():
    require(not [p for p in OUT if p.exists()], "Refusing to overwrite final-report figures")
    plt.style.use("seaborn-v0_8-whitegrid")

    # Fig. 1: existing citywide direction-hour rows, summarized for presentation.
    hourly = pd.read_csv(DATA / "metro_weather_hourly_merged.csv")
    pattern = hourly.groupby(["hour", "direction"], as_index=False)["ridership_count"].mean()
    fig, ax = plt.subplots(figsize=(9, 5))
    for direction, color in [("Entry", "#2a6fbb"), ("Exit", "#d05a34")]:
        part = pattern[pattern.direction == direction]
        ax.plot(part.hour, part.ridership_count, marker="o", linewidth=2, label=direction, color=color)
    ax.set(xlabel="Hour of day", ylabel="Mean citywide ridership count", xticks=range(24), title="Mean citywide hourly ridership by direction")
    ax.legend(title="Direction")
    fig.tight_layout(); fig.savefig(OUT[0], dpi=180); plt.close(fig)

    # Fig. 2: existing master station-hour records, summed for documented rankings.
    master = pd.read_csv(DATA / "metro_master.csv")
    stations = master.groupby("station name", as_index=False)["count"].sum().nlargest(10, "count").sort_values("count")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(stations["station name"], stations["count"] / 1e6, color="#356e9e")
    ax.set(xlabel="Cumulative passenger count (millions)", ylabel="Station", title="Top 10 stations by cumulative passenger count")
    fig.tight_layout(); fig.savefig(OUT[1], dpi=180); plt.close(fig)

    # Fig. 3: existing cleaned weather; show zero inflation and positive-rain magnitude.
    weather = pd.read_csv(DATA / "weather_hourly_cleaned.csv")
    rain = weather["rain_mm"].dropna()
    positive = rain[rain > 0]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    axes[0].bar(["No rain\n(0 mm)", "Positive rain\n(>0 mm)"], [(rain == 0).sum(), len(positive)], color=["#9aa5b1", "#3d8b5f"])
    axes[0].set(ylabel="Hourly observations", title="Hourly rainfall occurrence")
    axes[1].hist(positive, bins=min(25, max(5, len(positive))), color="#3d8b5f", edgecolor="white")
    axes[1].set(xlabel="Hourly rain (mm), conditional on rain", ylabel="Hourly observations", title="Distribution of positive hourly rain")
    fig.tight_layout(); fig.savefig(OUT[2], dpi=180); plt.close(fig)

    # Fig. 4: directly read the saved held-out test metrics; no refitting/scoring.
    stage7 = pd.read_csv(DATA / "stage9_consolidated_metrics.csv")
    stage7 = stage7[(stage7.stage == "Stage 7 advanced") & (stage7.split == "test") & stage7.model.isin(["RandomForest_A_temporal_history", "RandomForest_B_plus_weather"])]
    s10 = pd.read_csv(DATA / "stage10_spatial_weather_results.csv")
    s10 = s10[(s10.split == "test") & (s10.segment == "overall")][["model", "MAE", "RMSE"]].copy()
    s10["model"] = s10.model.map({"A_temporal_history": "A", "B_rajiv_chowk_weather": "B", "C_spatial_weather": "C spatial"})
    s11 = pd.read_csv(DATA / "stage11_forecast_weather_results.csv")
    s11 = s11[(s11.split == "test") & (s11.segment == "overall")][["model", "MAE", "RMSE"]].copy()
    s11["model"] = s11.model.map({"A_no_weather": "A", "B_observed_weather": "B", "C_forecast_rain": "C forecast"})
    panels = [("Stage 7: observed weather", stage7.assign(model=lambda x: x.model.map({"RandomForest_A_temporal_history": "A", "RandomForest_B_plus_weather": "B"}))), ("Stage 10: spatial rainfall", s10), ("Stage 11: forecast rainfall", s11)]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    for metric, ax in zip(["MAE", "RMSE"], axes):
        labels, values, colors = [], [], []
        for title, frame in panels:
            for _, row in frame.iterrows():
                labels.append(title.split(":")[0] + "\n" + row.model)
                values.append(row[metric])
                colors.append("#356e9e" if row.model == "A" else ("#ca6b39" if row.model == "B" else "#4b9b67"))
        ax.bar(np.arange(len(labels)), values, color=colors)
        ax.set(xticks=np.arange(len(labels)), xticklabels=labels, ylabel=metric, title=f"Held-out test {metric} by experiment")
        ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout(); fig.savefig(OUT[3], dpi=180); plt.close(fig)
    print("Created", *OUT, sep="\n")

if __name__ == "__main__":
    main()
