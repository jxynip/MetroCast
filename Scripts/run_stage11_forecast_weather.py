"""Stage 11: one-hour-ahead forecast-rain feasibility experiment.

Assumption set by the study owner: Metro HRn is [n:00, n+1:00) Asia/Kolkata.
Open-Meteo forecast rain values ending at :30 are interval-aligned by exact
half-hour overlap, never by rounding a timestamp.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
DATA, MODELS = ROOT / "DataProcessed", ROOT / "Models"
TARGET, KEYS = "ridership_count", ["time", "direction"]
LAT, LON = 28.646748, 77.17218
API = "https://single-runs-api.open-meteo.com/v1/forecast"
A = ["direction","month","is_peak_hour","hour_sin","hour_cos","dow_sin","dow_cos","ridership_lag_1h","ridership_lag_2h","ridership_lag_3h","ridership_lag_24h","ridership_rolling_mean_6h","ridership_rolling_mean_24h"]
F = ["forecast_rain_mm","forecast_rain_lag_1h","forecast_rain_lag_2h","forecast_rain_lag_3h","forecast_rain_sum_3h","forecast_rain_sum_6h","forecast_rain_sum_12h","forecast_rain_sum_24h"]
C = A + F
OUT_FEATURES = DATA / "stage11_forecast_rain_features.csv"
OUT_RESULTS = DATA / "stage11_forecast_weather_results.csv"
OUT_PREDS = DATA / "stage11_forecast_weather_predictions.csv"
OUT_SUMMARY = DATA / "stage11_forecast_weather_report.md"
OUT_MODEL = MODELS / "stage11_random_forest_forecast_rain.joblib"
OUT_RUN_CACHE = DATA / "stage11_forecast_run_cache.json"

def need(ok, message):
    if not ok: raise RuntimeError(message)

def score(y, p):
    e = np.asarray(p) - y.to_numpy(float)
    return {"n":len(y), "MAE":float(np.mean(np.abs(e))), "RMSE":float(np.sqrt(np.mean(e**2)))}

def model(option):
    numeric=[x for x in C if x != "direction"]
    return Pipeline([("preprocess", ColumnTransformer([("numeric",SimpleImputer(strategy="median"),numeric),("direction",OneHotEncoder(handle_unknown="ignore"),["direction"])])),("model",RandomForestRegressor(n_estimators=180,max_depth=[14,None][option],min_samples_leaf=[2,4][option],max_features=.8,n_jobs=-1,random_state=42))])

def selected_run(target):
    # target is local IST, decision is target-start minus one hour. All calculations below are UTC.
    target_utc = target - pd.Timedelta(hours=5, minutes=30)
    decision_utc = target_utc - pd.Timedelta(hours=1)
    latest_init = decision_utc - pd.Timedelta(hours=6)
    run = latest_init.floor("6h")
    return run, decision_utc, run + pd.Timedelta(hours=6)

def get_run(run):
    params={"latitude":LAT,"longitude":LON,"models":"ecmwf_ifs","hourly":"rain","timezone":"Asia/Kolkata","run":run.strftime("%Y-%m-%dT%H:%M"),"forecast_days":1}
    # The historical archive rate-limits bursts.  Retrying the identical
    # request does not change which run or weather values enter the study.
    response = None
    for attempt in range(12):
        try:
            response=requests.get(API,params=params,timeout=(15,45))
        except requests.RequestException:
            if attempt == 11: raise
            time.sleep(min(5 * (attempt + 1), 60))
            continue
        if response.status_code != 429:
            response.raise_for_status()
            break
        retry_after=response.headers.get("Retry-After")
        wait=float(retry_after) if retry_after and retry_after.isdigit() else min(5 * (attempt + 1), 60)
        time.sleep(wait)
    else:
        need(response is not None, f"No response for {run}")
        response.raise_for_status()
    body=response.json()
    need(body.get("timezone") == "Asia/Kolkata" and body.get("utc_offset_seconds") == 19800, f"Unexpected timezone for {run}")
    hourly=body["hourly"]
    return run, dict(zip(pd.to_datetime(hourly["time"]), hourly["rain"]))

def main():
    # The feature table may have been safely completed before a later model
    # step fails; preserve it and resume from the cached forecast inputs.
    outputs=[OUT_RESULTS,OUT_PREDS,OUT_SUMMARY,OUT_MODEL]
    need(not [p for p in outputs if p.exists()], "Refusing to overwrite Stage 11 outputs: "+", ".join(str(p) for p in outputs if p.exists()))
    manifest=json.loads((MODELS/"stage7_random_forest_manifest.json").read_text())
    need(manifest["models"]["RandomForest_A_temporal_history"]["features"] == A, "Stage 7 A schema mismatch")
    frames={n:pd.read_csv(DATA/f"metro_weather_{n}_prepared.csv",parse_dates=["time"]) for n in ["train","validation","test"]}
    all_times=pd.date_range("2024-09-01 00:00","2025-02-28 23:00",freq="h")
    selection={t:selected_run(t) for t in all_times}
    runs=sorted({x[0] for x in selection.values()})
    # Exactly one small (24 hour) API response per required eligible model run.
    # Persist completed runs so a transient archive outage never changes or
    # discards the selected-run set on resumption.
    cached=json.loads(OUT_RUN_CACHE.read_text()) if OUT_RUN_CACHE.exists() else {}
    forecast={pd.Timestamp(run):{pd.Timestamp(t):v for t,v in values.items()} for run,values in cached.items()}
    pending=[run for run in runs if run not in forecast]
    # Two concurrent requests are deliberately far below the original burst;
    # completed responses are checkpointed by the main thread.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(get_run, run):run for run in pending}
        for i, future in enumerate(as_completed(futures), start=len(forecast)+1):
            returned, values=future.result()
            forecast[returned]=values
            OUT_RUN_CACHE.write_text(json.dumps({str(r):{str(t):v for t,v in values.items()} for r,values in forecast.items()}))
            if i % 25 == 0 or i == len(runs): print(f"Retrieved {i}/{len(runs)} eligible forecast runs", flush=True)
    rows=[]
    for t in all_times:
        run, decision, available=selection[t]
        # Rain ending t+00:30 covers [t-00:30,t+00:30); rain ending t+01:30 covers [t+00:30,t+01:30).
        # Each overlaps Metro interval [t,t+01:00) for exactly 30 minutes.
        left, right=t+pd.Timedelta(minutes=30), t+pd.Timedelta(hours=1,minutes=30)
        values=forecast[run]
        need(left in values and right in values and values[left] is not None and values[right] is not None, f"Missing forecast bins for target {t} from run {run}")
        need(available <= decision, f"Availability policy failed for {t}")
        rows.append({"time":t,"target_interval_start_ist":t,"target_interval_end_ist":t+pd.Timedelta(hours=1),"decision_time_ist":t-pd.Timedelta(hours=1),"run_initialization_utc":run,"assumed_availability_utc":available,"forecast_valid_left_ist":left,"forecast_valid_right_ist":right,"forecast_lead_hours":(t-pd.Timedelta(hours=5,minutes=30)-run).total_seconds()/3600,"forecast_rain_mm":.5*float(values[left])+.5*float(values[right])})
    weather=pd.DataFrame(rows)
    for lag in [1,2,3]: weather[f"forecast_rain_lag_{lag}h"]=weather["forecast_rain_mm"].shift(lag)
    for window in [3,6,12,24]: weather[f"forecast_rain_sum_{window}h"]=weather["forecast_rain_mm"].shift(1).rolling(window,min_periods=window).sum()
    if OUT_FEATURES.exists():
        existing=pd.read_csv(OUT_FEATURES, parse_dates=["time"])
        need(len(existing)==len(weather) and existing["time"].equals(weather["time"]) and np.allclose(existing[F].to_numpy(float),weather[F].to_numpy(float),equal_nan=True), "Existing Stage 11 forecast features do not match cached runs")
    else:
        weather.to_csv(OUT_FEATURES,index=False)
    joined={}
    for n, frame in frames.items():
        x=frame.merge(weather[["time",*F,"run_initialization_utc","forecast_lead_hours"]],on="time",how="left",validate="many_to_one").sort_values(KEYS).reset_index(drop=True)
        need(len(x)==len(frame) and x[KEYS].equals(frame.sort_values(KEYS)[KEYS].reset_index(drop=True)), f"{n} keys changed")
        need(not x[C+[TARGET]].isna().any().any(), f"{n} has null Stage 11 inputs")
        joined[n]=x
    train,val,test=joined["train"],joined["validation"],joined["test"]
    need(train.time.max()<val.time.min()<test.time.min(),"nonchronological splits")
    candidates=[]
    for option in [0,1]:
        m=model(option).fit(train[C],train[TARGET]); candidates.append((option,m,score(val[TARGET],m.predict(val[C]))))
    option,_,val_c=min(candidates,key=lambda x:(x[2]["MAE"],x[2]["RMSE"]))
    final=model(option).fit(pd.concat([train,val]).sort_values(KEYS)[C],pd.concat([train,val]).sort_values(KEYS)[TARGET])
    need(list(final.feature_names_in_)==C,"Forecast model feature order mismatch")
    ma=joblib.load(MODELS/"random_forest_temporal_history.joblib"); mb=joblib.load(MODELS/"random_forest_temporal_weather.joblib")
    b=manifest["models"]["RandomForest_B_plus_weather"]["features"]
    need(list(ma.feature_names_in_)==A and list(mb.feature_names_in_)==b,"Saved model schema mismatch")
    predictions={"A_no_weather":ma.predict(test[A]),"B_observed_weather":mb.predict(test[b]),"C_forecast_rain":final.predict(test[C])}
    need(all(np.isfinite(p).all() for p in predictions.values()),"nonfinite prediction")
    result=[]; predrows=[]
    def add(segment, mask):
        local=test.loc[mask].reset_index(drop=True)
        ps={k:v[mask] for k,v in predictions.items()}
        stats={k:score(local[TARGET],v) for k,v in ps.items()}
        for name,s in stats.items(): result.append({"split":"test","segment":segment,"model":name,**s,"MAE_minus_A":s["MAE"]-stats["A_no_weather"]["MAE"],"RMSE_minus_A":s["RMSE"]-stats["A_no_weather"]["RMSE"]})
    add("overall",np.ones(len(test),dtype=bool)); add("Entry",test.direction.eq("Entry").to_numpy()); add("Exit",test.direction.eq("Exit").to_numpy())
    for name,p in predictions.items():
        predrows.append(pd.DataFrame({"split":"test","model":name,"time":test.time,"direction":test.direction,"actual":test[TARGET],"prediction":p,"forecast_rain_mm":test["forecast_rain_mm"],"run_initialization_utc":test["run_initialization_utc"],"forecast_lead_hours":test["forecast_lead_hours"]}))
    for option_,_,s in candidates: result.append({"split":"validation","segment":f"C_candidate_option_{option_}","model":"C_forecast_rain",**s,"MAE_minus_A":np.nan,"RMSE_minus_A":np.nan})
    results=pd.DataFrame(result); preds=pd.concat(predrows,ignore_index=True)
    results.to_csv(OUT_RESULTS,index=False); preds.to_csv(OUT_PREDS,index=False); joblib.dump(final,OUT_MODEL)
    overall=results.query("split == 'test' and segment == 'overall'").set_index("model")
    a,brow,crow=(overall.loc[x] for x in ["A_no_weather","B_observed_weather","C_forecast_rain"])
    summary=f"""# Stage 11 — genuine one-hour-ahead forecast-rain experiment\n\n**Status:** complete, under the user-specified Metro convention `HRn = [n:00, (n+1):00) IST`. This convention was not independently documented in the source workbook.\n\n## Availability and interval policy\n\nFor target interval `[T, T+1h) IST`, decision time is `T-1h`. A selected ECMWF IFS HRES run must satisfy `run initialization + 6h <= decision time`; six hours is a conservative assumption, not a verified historical dissemination timestamp. Forecast rain bins ending at `T+00:30` and `T+01:30` each overlap the target interval for 30 minutes, so `forecast_rain_mm = 0.5 * left + 0.5 * right`. No timestamp rounding was used. This weighting assumes uniform precipitation within each one-hour model bin.\n\n## Model protocol\n\n- Unchanged chronological splits and target `ridership_count`: train {len(train)}, validation {len(val)}, test {len(test)}.\n- A and B are the untouched persisted Stage 7 artifacts. B uses observed same-hour multi-weather inputs and remains retrospective.\n- C uses A features plus issued forecast-rain and its forecast-only 1/2/3-hour lags and preceding 3/6/12/24-hour sums. C option {option} was selected solely on validation MAE, RMSE tie-break, then refit on train + validation; test was scored once.\n\n## Test results\n\n| Model | MAE | RMSE | MAE vs A |\n|---|---:|---:|---:|\n| A no weather | {a.MAE:.3f} | {a.RMSE:.3f} | 0.000 |\n| B observed weather | {brow.MAE:.3f} | {brow.RMSE:.3f} | {brow.MAE_minus_A:.3f} |\n| C forecast rain | {crow.MAE:.3f} | {crow.RMSE:.3f} | {crow.MAE_minus_A:.3f} |\n\nForecast-run, lead-time, and interval audit fields are in `{OUT_FEATURES.name}`; complete paired test predictions are in `{OUT_PREDS.name}`. Results do not support causal claims.\n"""
    OUT_SUMMARY.write_text(summary)
    print(results.to_string(index=False)); print("Created", OUT_SUMMARY)

if __name__ == "__main__": main()
