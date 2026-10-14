from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "DataRaw" / "delhi_metro_weather_5_locations_2024_2025.csv.csv"
DATA_DIR = PROJECT_ROOT / "DataProcessed"

OUTPUT_PATHS = [
    DATA_DIR / "spatial_weather_locations_hourly.csv",
    DATA_DIR / "spatial_weather_hourly_features.csv",
    DATA_DIR / "metro_spatial_weather_features.csv",
    DATA_DIR / "spatial_weather_validation_summary.csv",
]

METADATA_COLUMNS = [
    "location_id",
    "metadata_latitude",
    "metadata_longitude",
    "elevation_m",
    "utc_offset_seconds",
    "timezone",
    "timezone_abbreviation",
]
OBSERVATION_RENAME = {
    "precipitation (mm)": "precipitation_mm",
    "rain (mm)": "rain_mm",
    "temperature_2m (°C)": "temperature_2m_c",
    "relative_humidity_2m (%)": "relative_humidity_2m_pct",
    "apparent_temperature (°C)": "apparent_temperature_c",
    "weather_code (wmo code)": "weather_code_wmo",
    "surface_pressure (hPa)": "surface_pressure_hpa",
    "cloud_cover (%)": "cloud_cover_pct",
    "wind_speed_10m (km/h)": "wind_speed_10m_kmh",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0088
    lat1_rad, lat2_rad = np.radians([lat1, lat2])
    delta_lat = np.radians(lat2 - lat1)
    delta_lon = np.radians(lon2 - lon1)
    value = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2) ** 2
    )
    return float(2 * earth_radius_km * np.arcsin(np.sqrt(value)))


def main() -> None:
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(f"Required spatial-weather input is missing: {SOURCE_PATH}")
    existing_outputs = [path for path in OUTPUT_PATHS if path.exists()]
    if existing_outputs:
        raise FileExistsError(
            "Refusing to overwrite existing outputs: "
            + ", ".join(str(path) for path in existing_outputs)
        )

    metadata = pd.read_csv(SOURCE_PATH, nrows=5)
    metadata.columns = METADATA_COLUMNS
    observations = pd.read_csv(SOURCE_PATH, skiprows=7)
    observations = observations.rename(columns=OBSERVATION_RENAME)

    required_columns = ["location_id", "time", *OBSERVATION_RENAME.values()]
    missing_columns = set(required_columns) - set(observations.columns)
    if missing_columns:
        raise ValueError(f"Weather observations missing required columns: {sorted(missing_columns)}")
    if metadata["location_id"].duplicated().any():
        raise ValueError("Location metadata contains duplicate location_id values.")

    metadata["location_id"] = pd.to_numeric(metadata["location_id"], errors="raise").astype(int)
    metadata["metadata_latitude"] = pd.to_numeric(metadata["metadata_latitude"], errors="raise")
    metadata["metadata_longitude"] = pd.to_numeric(metadata["metadata_longitude"], errors="raise")
    metadata["elevation_m"] = pd.to_numeric(metadata["elevation_m"], errors="raise")
    metadata["utc_offset_seconds"] = pd.to_numeric(metadata["utc_offset_seconds"], errors="raise").astype(int)
    observations["location_id"] = pd.to_numeric(observations["location_id"], errors="raise").astype(int)
    observations["time"] = pd.to_datetime(observations["time"], errors="coerce")
    if observations["time"].isna().any():
        raise ValueError("Invalid or missing observation timestamps found.")

    expected_location_ids = set(metadata["location_id"])
    if len(expected_location_ids) != 5 or set(observations["location_id"].unique()) != expected_location_ids:
        raise ValueError("Expected exactly five metadata locations with matching observation location_id values.")
    if set(metadata["timezone"]) != {"Asia/Kolkata"} or set(metadata["utc_offset_seconds"]) != {19800}:
        raise ValueError("Unexpected timezone metadata; expected Asia/Kolkata (UTC+05:30).")
    if not metadata["metadata_latitude"].between(-90, 90).all() or not metadata["metadata_longitude"].between(-180, 180).all():
        raise ValueError("Invalid latitude/longitude metadata values.")

    numeric_weather = list(OBSERVATION_RENAME.values())
    for column in numeric_weather:
        observations[column] = pd.to_numeric(observations[column], errors="coerce")
    if observations[required_columns].isna().any().any():
        missing = observations[required_columns].isna().sum()
        raise ValueError(f"Missing weather observations found: {missing[missing.gt(0)].to_dict()}")
    if observations.duplicated(["location_id", "time"]).any():
        raise ValueError("Duplicate location_id/time records found.")

    expected_times = pd.date_range("2024-09-01 00:00", "2025-02-28 23:00", freq="h")
    if len(expected_times) != 4344:
        raise AssertionError("Unexpected expected hourly timeline length.")
    coverage_rows = []
    for location_id in sorted(expected_location_ids):
        location = observations.loc[observations["location_id"].eq(location_id)]
        actual_times = pd.DatetimeIndex(location["time"].sort_values().unique())
        missing_times = expected_times.difference(actual_times)
        extra_times = actual_times.difference(expected_times)
        coverage_rows.append({
            "location_id": location_id,
            "observation_rows": len(location),
            "unique_timestamps": len(actual_times),
            "expected_timestamps": len(expected_times),
            "missing_timestamps": len(missing_times),
            "unexpected_timestamps": len(extra_times),
            "duplicate_location_time_records": int(location.duplicated(["location_id", "time"]).sum()),
        })
        if len(location) != len(expected_times) or len(missing_times) or len(extra_times):
            raise ValueError(f"Incomplete hourly coverage for location_id={location_id}.")
        if not actual_times.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all():
            raise ValueError(f"Non-hourly timestamp gap for location_id={location_id}.")

    bounds = {
        "precipitation_mm": observations["precipitation_mm"].ge(0).all(),
        "rain_mm": observations["rain_mm"].ge(0).all(),
        "relative_humidity_2m_pct": observations["relative_humidity_2m_pct"].between(0, 100).all(),
        "cloud_cover_pct": observations["cloud_cover_pct"].between(0, 100).all(),
        "wind_speed_10m_kmh": observations["wind_speed_10m_kmh"].ge(0).all(),
        "weather_code_wmo": observations["weather_code_wmo"].ge(0).all(),
    }
    if not all(bounds.values()):
        raise ValueError(f"Weather values outside basic physical/code bounds: {bounds}")

    metadata_by_location = metadata.set_index("location_id")
    locations = observations.merge(
        metadata.reset_index(drop=True), on="location_id", how="left", validate="many_to_one"
    )
    if locations["metadata_latitude"].isna().any():
        raise ValueError("Some observation location_id values lack metadata.")
    locations = locations.sort_values(["location_id", "time"]).reset_index(drop=True)

    coordinate_table = metadata.set_index("location_id")[["metadata_latitude", "metadata_longitude"]]
    coordinate_rows = []
    coordinate_duplicates = coordinate_table.duplicated(keep=False)
    for location_id, row in coordinate_table.iterrows():
        other_distances = {
            other_id: haversine_km(row.metadata_latitude, row.metadata_longitude, other.metadata_latitude, other.metadata_longitude)
            for other_id, other in coordinate_table.iterrows() if other_id != location_id
        }
        nearest_id = min(other_distances, key=other_distances.get)
        nearest_distance = other_distances[nearest_id]
        coordinate_rows.append({
            "location_id": location_id,
            "metadata_latitude": row.metadata_latitude,
            "metadata_longitude": row.metadata_longitude,
            "exact_duplicate_coordinate": bool(coordinate_duplicates.loc[location_id]),
            "nearest_location_id": nearest_id,
            "nearest_location_distance_km": nearest_distance,
            "possible_same_coarse_grid_cell_under_10km": bool(nearest_distance < 10),
            "requested_coordinates_available_in_file": False,
            "request_match_status": "UNVERIFIABLE: CSV stores one coordinate record per location_id, but no separate requested-coordinate manifest was supplied.",
        })
    coordinate_validation = pd.DataFrame(coordinate_rows)

    spatial = locations.groupby("time", as_index=False).agg(
        spatial_rain_mean_mm=("rain_mm", "mean"),
        spatial_rain_max_mm=("rain_mm", "max"),
        rain_locations_count=("rain_mm", lambda values: int(values.gt(0).sum())),
    ).sort_values("time").reset_index(drop=True)
    if len(spatial) != len(expected_times) or not spatial["time"].equals(pd.Series(expected_times, name="time")):
        raise ValueError("Spatial summary does not cover the complete expected hourly timeline.")

    # Historical rain features use the full location-aggregated weather clock before any ridership join.
    for lag in [1, 2, 3]:
        lag_lookup = spatial[["time", "spatial_rain_mean_mm"]].copy()
        lag_lookup["time"] += pd.Timedelta(hours=lag)
        lag_lookup = lag_lookup.rename(columns={"spatial_rain_mean_mm": f"spatial_rain_mean_lag_{lag}h"})
        spatial = spatial.merge(lag_lookup, on="time", how="left", validate="one_to_one")
    rain_series = spatial.set_index("time")["spatial_rain_mean_mm"]
    for window in [3, 6, 12, 24]:
        spatial[f"spatial_rain_mean_sum_{window}h"] = rain_series.rolling(
            f"{window}h", closed="left", min_periods=window
        ).sum().to_numpy()
    spatial = spatial.sort_values("time").reset_index(drop=True)

    temporal_path = DATA_DIR / "metro_weather_temporal_features.csv"
    if not temporal_path.is_file():
        raise FileNotFoundError(f"Existing Metro temporal dataset missing: {temporal_path}")
    metro = pd.read_csv(temporal_path, parse_dates=["time"]).sort_values(["time", "direction"]).reset_index(drop=True)
    if metro.duplicated(["time", "direction"]).any():
        raise ValueError("Existing Metro dataset has duplicate time/direction keys.")
    if not set(metro["direction"].unique()).issubset({"Entry", "Exit"}):
        raise ValueError("Unexpected direction values in existing Metro data.")

    enriched = metro.merge(spatial, on="time", how="left", validate="many_to_one", indicator=True)
    if not enriched["_merge"].eq("both").all():
        raise ValueError("Some Metro timestamps are not covered by the full spatial-weather timeline.")
    enriched = enriched.drop(columns="_merge").sort_values(["time", "direction"]).reset_index(drop=True)
    if len(enriched) != len(metro) or not enriched[["time", "direction"]].equals(metro[["time", "direction"]]):
        raise AssertionError("Spatial join changed Metro rows, timestamp order, or Entry/Exit keys.")
    if not enriched["rain_locations_count"].between(0, 5).all():
        raise ValueError("Invalid rainy-location count.")

    validation = pd.DataFrame(coverage_rows).merge(coordinate_validation, on="location_id", validate="one_to_one")
    validation.insert(0, "source_file", SOURCE_PATH.name)
    legacy_weather_path = PROJECT_ROOT / "DataRaw" / "Weather_RC_5month.csv"
    if not legacy_weather_path.is_file():
        raise FileNotFoundError(f"Existing Rajiv Chowk weather metadata is missing: {legacy_weather_path}")
    legacy_metadata = pd.read_csv(legacy_weather_path, nrows=1)
    if not {"latitude", "longitude"}.issubset(legacy_metadata.columns):
        raise ValueError("Could not read Rajiv Chowk coordinate metadata from existing weather source.")
    rajiv_latitude = float(legacy_metadata.loc[0, "latitude"])
    rajiv_longitude = float(legacy_metadata.loc[0, "longitude"])
    loc0 = metadata.loc[metadata.location_id.eq(0)].iloc[0]
    loc0_matches_rajiv = bool(
        np.isclose(loc0.metadata_latitude, rajiv_latitude, atol=1e-6)
        and np.isclose(loc0.metadata_longitude, rajiv_longitude, atol=1e-6)
    )
    validation["coordinate_matches_existing_rajiv_point"] = validation.location_id.eq(0) & loc0_matches_rajiv
    validation["requested_coordinate_comparison_note"] = (
        f"Metadata coordinates are recorded in this CSV, but separate requested coordinates are unavailable. "
        f"location_id 0 {'matches' if loc0_matches_rajiv else 'does not match'} the existing Rajiv Chowk source coordinate "
        f"({rajiv_latitude}, {rajiv_longitude}); requested coordinates for location_id 1-4 are unverified."
    )
    validation["units_and_range_checks"] = "PASS: rain/precipitation >= 0 mm; RH/cloud 0-100%; wind >= 0 km/h; WMO code nonnegative"
    validation["global_observation_missing_cells"] = int(locations[numeric_weather].isna().sum().sum())
    validation["global_duplicate_location_time_keys"] = int(locations.duplicated(["location_id", "time"]).sum())
    validation["spatial_summary_timestamps"] = len(spatial)
    validation["metro_input_rows"] = len(metro)
    validation["metro_enriched_rows"] = len(enriched)
    validation["metro_unmatched_rows"] = int(enriched["spatial_rain_mean_mm"].isna().sum())

    output_map = {
        "location_level": DATA_DIR / "spatial_weather_locations_hourly.csv",
        "hourly_features": DATA_DIR / "spatial_weather_hourly_features.csv",
        "metro_enriched": DATA_DIR / "metro_spatial_weather_features.csv",
        "validation": DATA_DIR / "spatial_weather_validation_summary.csv",
    }
    existing = [path for path in output_map.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing spatial outputs: " + ", ".join(map(str, existing)))

    locations.to_csv(output_map["location_level"], index=False)
    spatial.to_csv(output_map["hourly_features"], index=False)
    enriched.to_csv(output_map["metro_enriched"], index=False)
    validation.to_csv(output_map["validation"], index=False)

    print("Input:", SOURCE_PATH)
    print("Metadata coordinates (not independently verified against request coordinates):")
    print(coordinate_validation.to_string(index=False))
    print("Coverage:")
    print(validation[["location_id", "observation_rows", "unique_timestamps", "missing_timestamps", "duplicate_location_time_records", "nearest_location_distance_km", "possible_same_coarse_grid_cell_under_10km"]].to_string(index=False))
    print("Spatial hourly rows:", len(spatial), "| Metro input/enriched rows:", len(metro), len(enriched))
    print("Spatial rainfall feature missing counts:", spatial.isna().sum().to_dict())
    print("Created:")
    for path in output_map.values():
        print(path)


if __name__ == "__main__":
    main()
