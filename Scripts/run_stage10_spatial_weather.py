"""Controlled, retrospective Stage 10 spatial-weather Random Forest experiment.

Creates new Stage 10 outputs only.  It intentionally never writes to existing
Stage 7 artifacts, prepared splits, predictions, or notebooks.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "DataProcessed"
MODELS = ROOT / "Models"
TARGET = "ridership_count"
KEYS = ["time", "direction"]

STAGE7_MANIFEST = MODELS / "stage7_random_forest_manifest.json"
STAGE7_A = MODELS / "random_forest_temporal_history.joblib"
STAGE7_B = MODELS / "random_forest_temporal_weather.joblib"

OUT_MODEL = MODELS / "stage10_random_forest_spatial_weather.joblib"
OUT_RESULTS = DATA / "stage10_spatial_weather_results.csv"
OUT_SUMMARY = DATA / "stage10_spatial_weather_summary.md"

FEATURES_A = [
    "direction", "month", "is_peak_hour", "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "ridership_lag_1h", "ridership_lag_2h", "ridership_lag_3h", "ridership_lag_24h",
    "ridership_rolling_mean_6h", "ridership_rolling_mean_24h",
]
SPATIAL_FEATURES = [
    "spatial_rain_mean_mm", "spatial_rain_max_mm", "rain_locations_count",
    "spatial_rain_mean_lag_1h", "spatial_rain_mean_lag_2h", "spatial_rain_mean_lag_3h",
    "spatial_rain_mean_sum_3h", "spatial_rain_mean_sum_6h",
    "spatial_rain_mean_sum_12h", "spatial_rain_mean_sum_24h",
]
FEATURES_C = FEATURES_A + SPATIAL_FEATURES


def metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float | int]:
    error = np.asarray(predicted, dtype=float) - actual.to_numpy(dtype=float)
    return {
        "n": len(actual),
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
    }


def pipeline(features: list[str], option: int) -> Pipeline:
    numeric = [feature for feature in features if feature != "direction"]
    estimator = RandomForestRegressor(
        n_estimators=180,
        max_depth=[14, None][option],
        min_samples_leaf=[2, 4][option],
        max_features=0.8,
        n_jobs=-1,
        random_state=42,
    )
    preprocess = ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median"), numeric),
        ("direction", OneHotEncoder(handle_unknown="ignore"), ["direction"]),
    ])
    return Pipeline([("preprocess", preprocess), ("model", estimator)])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def add_metric_rows(
    rows: list[dict[str, object]],
    split: str,
    segment: str,
    frame: pd.DataFrame,
    predictions: dict[str, np.ndarray],
) -> None:
    values = {name: metrics(frame[TARGET], prediction) for name, prediction in predictions.items()}
    for model, value in values.items():
        rows.append({
            "split": split,
            "segment": segment,
            "model": model,
            "n": value["n"],
            "MAE": value["MAE"],
            "RMSE": value["RMSE"],
            "MAE_minus_A": value["MAE"] - values["A_temporal_history"]["MAE"],
            "RMSE_minus_A": value["RMSE"] - values["A_temporal_history"]["RMSE"],
            "MAE_minus_B": value["MAE"] - values["B_rajiv_chowk_weather"]["MAE"],
            "RMSE_minus_B": value["RMSE"] - values["B_rajiv_chowk_weather"]["RMSE"],
        })


def main() -> None:
    outputs = [OUT_MODEL, OUT_RESULTS, OUT_SUMMARY]
    existing = [path for path in outputs if path.exists()]
    require(not existing, "Refusing to overwrite Stage 10 output(s): " + ", ".join(map(str, existing)))

    with STAGE7_MANIFEST.open() as handle:
        manifest = json.load(handle)
    require(manifest["target"] == TARGET, "Stage 7 target does not match Stage 10 target.")
    require(manifest["models"]["RandomForest_A_temporal_history"]["features"] == FEATURES_A,
            "Stage 7 Model A schema does not match the controlled schema.")

    splits = {
        name: pd.read_csv(DATA / f"metro_weather_{name}_prepared.csv", parse_dates=["time"])
        for name in ["train", "validation", "test"]
    }
    spatial = pd.read_csv(DATA / "metro_spatial_weather_features.csv", parse_dates=["time"])
    require(not spatial.duplicated(KEYS).any(), "Spatial input has duplicate (time, direction) keys.")
    # The full weather timeline has valid warm-up nulls before prepared splits begin;
    # null-free spatial features are enforced below for every actual model input row.
    require(not spatial[KEYS + [TARGET]].isna().any().any(),
            "Spatial input has null key or target values.")

    enriched: dict[str, pd.DataFrame] = {}
    for name, frame in splits.items():
        require(not frame.duplicated(KEYS).any(), f"{name} split has duplicate keys.")
        require(frame[KEYS].equals(frame.sort_values(KEYS)[KEYS].reset_index(drop=True)),
                f"{name} split is not sorted by (time, direction).")
        require(frame[TARGET].notna().all(), f"{name} target contains nulls.")
        require(not frame[FEATURES_A].isna().any().any(), f"{name} has null Model A inputs.")
        right = spatial[KEYS + [TARGET] + SPATIAL_FEATURES].rename(columns={TARGET: "_spatial_target"})
        joined = frame.merge(right, on=KEYS, how="left", validate="one_to_one", indicator=True)
        require(joined["_merge"].eq("both").all(), f"{name} has keys absent from spatial data.")
        require(np.array_equal(joined[TARGET].to_numpy(), joined["_spatial_target"].to_numpy()),
                f"{name} target does not exactly match spatial data by key.")
        joined = joined.drop(columns=["_merge", "_spatial_target"]).sort_values(KEYS).reset_index(drop=True)
        require(joined[KEYS].equals(frame[KEYS].reset_index(drop=True)), f"{name} join changed key order.")
        require(not joined[FEATURES_C].isna().any().any(), f"{name} has null Model C inputs.")
        enriched[name] = joined

    train, validation, test = enriched["train"], enriched["validation"], enriched["test"]
    require(train.time.max() < validation.time.min() < test.time.min(), "Splits are not chronological.")
    require(not set(FEATURES_C).intersection({TARGET, "time"}), "Target or time entered Model C features.")
    require(not set(SPATIAL_FEATURES).intersection(set(manifest["models"]["RandomForest_B_plus_weather"]["features"])),
            "Model C spatial-only schema overlaps Model B Rajiv Chowk weather schema.")

    validation_options: list[dict[str, object]] = []
    candidates: dict[int, Pipeline] = {}
    for option in [0, 1]:
        candidate = pipeline(FEATURES_C, option)
        candidate.fit(train[FEATURES_C], train[TARGET])
        score = metrics(validation[TARGET], candidate.predict(validation[FEATURES_C]))
        validation_options.append({"option": option, **score})
        candidates[option] = candidate
    selected = min(validation_options, key=lambda row: (float(row["MAE"]), float(row["RMSE"])))
    selected_option = int(selected["option"])

    # Existing A/B validation scores were obtained with the same train-only protocol in Stage 7.
    stage7_val = manifest["validation_model_selection"]["models"]
    selection_table = [
        {"model": "A_temporal_history", "MAE": stage7_val["RandomForest_A_temporal_history"]["validation_MAE"], "RMSE": stage7_val["RandomForest_A_temporal_history"]["validation_RMSE"]},
        {"model": "B_rajiv_chowk_weather", "MAE": stage7_val["RandomForest_B_plus_weather"]["validation_MAE"], "RMSE": stage7_val["RandomForest_B_plus_weather"]["validation_RMSE"]},
        {"model": "C_spatial_weather", "MAE": selected["MAE"], "RMSE": selected["RMSE"]},
    ]
    validation_winner = min(selection_table, key=lambda row: (float(row["MAE"]), float(row["RMSE"])))

    # Stage 7 protocol: refit the validation-selected configuration using train+validation only.
    train_validation = pd.concat([train, validation], ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    final_c = pipeline(FEATURES_C, selected_option)
    final_c.fit(train_validation[FEATURES_C], train_validation[TARGET])
    require(list(final_c.feature_names_in_) == FEATURES_C, "Model C feature order changed after fitting.")

    model_a = joblib.load(STAGE7_A)
    model_b = joblib.load(STAGE7_B)
    features_b = manifest["models"]["RandomForest_B_plus_weather"]["features"]
    require(list(model_a.feature_names_in_) == FEATURES_A, "Saved Model A feature order differs from manifest.")
    require(list(model_b.feature_names_in_) == features_b, "Saved Model B feature order differs from manifest.")
    require(not test[features_b].isna().any().any(), "Test has null Model B inputs.")

    test_predictions = {
        "A_temporal_history": np.asarray(model_a.predict(test[FEATURES_A]), dtype=float),
        "B_rajiv_chowk_weather": np.asarray(model_b.predict(test[features_b]), dtype=float),
        "C_spatial_weather": np.asarray(final_c.predict(test[FEATURES_C]), dtype=float),
    }
    require(all(np.isfinite(value).all() and len(value) == len(test) for value in test_predictions.values()),
            "A, B, or C produced nonfinite or misaligned test predictions.")

    rows: list[dict[str, object]] = []
    for option_result in validation_options:
        rows.append({
            "split": "validation", "segment": f"C_candidate_option_{option_result['option']}",
            "model": "C_spatial_weather", "n": option_result["n"], "MAE": option_result["MAE"],
            "RMSE": option_result["RMSE"], "MAE_minus_A": np.nan, "RMSE_minus_A": np.nan,
            "MAE_minus_B": np.nan, "RMSE_minus_B": np.nan,
        })
    add_metric_rows(rows, "test", "overall", test, test_predictions)
    for direction in ["Entry", "Exit"]:
        mask = test.direction.eq(direction).to_numpy()
        add_metric_rows(rows, "test", direction, test.loc[mask].reset_index(drop=True),
                        {name: values[mask] for name, values in test_predictions.items()})
    # Descriptive, predeclared hourly intensity bands based on spatial maximum rain (mm).
    bands = [("dry_0mm", -np.inf, 0.0), ("light_0_to_2.5mm", 0.0, 2.5),
             ("moderate_2.5_to_7.6mm", 2.5, 7.6), ("heavy_over_7.6mm", 7.6, np.inf)]
    for label, lower, upper in bands:
        if lower == -np.inf:
            mask = test.spatial_rain_max_mm.eq(0).to_numpy()
        elif upper == np.inf:
            mask = test.spatial_rain_max_mm.gt(lower).to_numpy()
        else:
            mask = test.spatial_rain_max_mm.gt(lower).to_numpy() & test.spatial_rain_max_mm.le(upper).to_numpy()
        if int(mask.sum()):
            add_metric_rows(rows, "test", label, test.loc[mask].reset_index(drop=True),
                            {name: values[mask] for name, values in test_predictions.items()})
        else:
            for model in test_predictions:
                rows.append({"split": "test", "segment": label, "model": model, "n": 0,
                             "MAE": np.nan, "RMSE": np.nan, "MAE_minus_A": np.nan,
                             "RMSE_minus_A": np.nan, "MAE_minus_B": np.nan, "RMSE_minus_B": np.nan})
    results = pd.DataFrame(rows)

    joblib.dump(final_c, OUT_MODEL)
    results.to_csv(OUT_RESULTS, index=False)
    overall = results.query("split == 'test' and segment == 'overall'").set_index("model")
    heavy_n = int(results.query("split == 'test' and segment == 'heavy_over_7.6mm'")["n"].iloc[0])
    summary = f"""# Stage 10: controlled spatial-weather experiment

Status: completed. This is a retrospective comparison: Models B and C use observed same-hour weather. It does not establish operational forecasting performance or causality.

## Protocol verification

- Target: `{TARGET}`. Exact `(time, direction)` keys and target values matched between each prepared split and spatial dataset.
- Rows: train {len(train)}, validation {len(validation)}, test {len(test)}; chronological boundaries are preserved.
- Model C feature order ({len(FEATURES_C)} fields): `{', '.join(FEATURES_C)}`.
- C excludes all Rajiv Chowk weather fields. Inputs were null-free before fitting.
- RF candidates matched Stage 7: 180 trees, `max_features=0.8`, `n_jobs=-1`, `random_state=42`; option 0 = depth 14/leaf 2 and option 1 = unrestricted depth/leaf 4.
- C selected option {selected_option} by validation MAE, RMSE tie-break. Across the recorded Stage 7 A/B validation results and C, the validation winner was `{validation_winner['model']}`.
- C was refit on train + validation only; test was evaluated once. Existing A/B test artifacts were reused unchanged.

## Test overall results

| Model | MAE | RMSE | MAE minus A | MAE minus B |
| --- | ---: | ---: | ---: | ---: |
"""
    for model in ["A_temporal_history", "B_rajiv_chowk_weather", "C_spatial_weather"]:
        row = overall.loc[model]
        summary += f"| {model} | {row.MAE:.3f} | {row.RMSE:.3f} | {row.MAE_minus_A:.3f} | {row.MAE_minus_B:.3f} |\n"
    summary += f"""

Direction-specific and rain-band metrics, including sample counts, are in `{OUT_RESULTS.name}`. Rain bands are descriptive and use spatial maximum hourly rain: dry = 0 mm, light = (0, 2.5] mm, moderate = (2.5, 7.6] mm, heavy > 7.6 mm. Heavy-rain n is {heavy_n}; evidence is insufficient for a reliable heavy-rain conclusion when this count is small.
"""
    OUT_SUMMARY.write_text(summary)
    print(f"Created: {OUT_MODEL}\nCreated: {OUT_RESULTS}\nCreated: {OUT_SUMMARY}")
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
