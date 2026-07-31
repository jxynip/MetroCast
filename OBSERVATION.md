# in version 1.1
while doing EDA on the 5 month dataset

## Data Validation

The dataset was validated after preprocessing to ensure that all monthly entry and exit sheets were correctly merged into a single master dataset.

### Validation Checks

- All six months (September 2024 – February 2025) were successfully imported.
- Entry and exit datasets contained nearly identical numbers of records.
  - Entry records: **936,243**
  - Exit records: **936,222**
- The 21-record difference was found only in the December dataset and is negligible (<0.003% of all records).

### Passenger Count Observation

During exploratory data analysis, the source dataset consistently reported higher exit counts than entry counts across every month.

| Direction | Total Passenger Count |
|-----------|----------------------:|
| Entry | 518,847,146 |
| Exit | 559,994,662 |

The difference is approximately **41.15 million passengers (≈7.9%)**.

Additional validation showed that:

- The discrepancy exists across all six months.
- The average passenger count per station-hour record is higher for exit data than for entry data.
- No evidence was found that the discrepancy resulted from the preprocessing pipeline.

Based on these checks, the difference is treated as a characteristic of the original dataset rather than a data-processing error. Both entry and exit datasets are retained without modification.

# version 1.2 observations
# Exploratory Data Analysis (EDA)

## Dataset Overview

- Dataset period: **September 2024 – February 2025**
- Contains station-wise hourly Delhi Metro ridership.
- Passenger movements are categorized as **Entry** and **Exit**.
- Final merged dataset contains **1,872,465** station-hour observations with the following columns:
  - `businessday`
  - `linename`
  - `sitename`
  - `station name`
  - `station code`
  - `hour`
  - `count`
  - `month`
  - `direction`

---

## Data Validation

- Entry records: **936,243**
- Exit records: **936,222**

The dataset differs by only **21 records**, all belonging to the December dataset, indicating that the preprocessing pipeline successfully merged the source files.

---

## Hourly Ridership Pattern

Hourly passenger volume follows a clear daily commuting pattern.

### Observations

- Ridership begins increasing rapidly after **6 AM**.
- Morning demand peaks around **9 AM**.
- Passenger counts decline during the afternoon.
- A second and slightly larger peak occurs around **6 PM (18:00)**.
- Ridership steadily decreases after **8 PM**.
- Very low passenger movement is observed between **12 AM–5 AM**.

---

## Busiest Metro Stations

Top stations by cumulative passenger volume:

| Rank | Station |
|------|-------------------------------|
| 1 | New Delhi |
| 2 | Chandni Chowk |
| 3 | Millennium City Centre Gurugram |
| 4 | Kashmere Gate |
| 5 | Rajiv Chowk |
| 6 | Karol Bagh |
| 7 | Saket |
| 8 | Dwarka Mor |
| 9 | Anand Vihar ISBT |
| 10 | Sector-52 Noida |

### Observation

Passenger demand is concentrated around major interchange stations, commercial hubs, and high-density residential areas.

---

## Metro Line Analysis

Total passenger volume by metro line shows an uneven distribution of demand.

### Observations

- **LINE02** recorded the highest passenger volume.
- **LINE03** recorded the second-highest passenger volume.
- **LINE06**, **LINE01**, and **LINE07** also carried substantial traffic.
- **RMGL (Airport Express)** recorded the lowest passenger volume among the major lines.

Passenger demand is concentrated on a relatively small number of metro corridors.

---

## Entry vs Exit by Metro Line

Comparison of cumulative entries and exits for each metro line shows:

- Exit counts exceed entry counts for every metro line.
- The ranking of metro lines remains consistent for both Entry and Exit traffic.
- High-volume lines exhibit similar entry and exit distributions.

---

## Overall Passenger Volume

| Direction | Total Passengers |
|-----------|-----------------:|
| Entry | 518,847,146 |
| Exit | 559,994,662 |

### Observation

- Exit passenger counts exceed entry passenger counts by approximately **41.15 million passengers (~7.9%)**.
- The difference is consistently observed across every month and metro line.

---

## Monthly Validation

Monthly passenger totals remain relatively stable throughout the study period.

Additional observations:

- Exit totals exceed Entry totals in every month.
- The entry-exit imbalance is therefore not isolated to a particular month.

---

## Descriptive Statistics

Average passengers per station-hour:

| Direction | Mean | Median | Maximum |
|-----------|-----:|-------:|--------:|
| Entry | 554.18 | 287 | 13,486 |
| Exit | 598.14 | 306 | 15,152 |

### Observations

- Exit records have a higher average passenger count than Entry records.
- Mean values are considerably higher than median values, indicating a positively skewed distribution.
- A small number of station-hour combinations experience extremely high passenger volumes.

---

## Summary

The exploratory analysis indicates that:

- Delhi Metro exhibits a clear bimodal daily commuting pattern, with morning and evening peaks.
- Passenger demand is concentrated on a small number of metro lines and stations.
- Exit passenger counts consistently exceed Entry counts throughout the dataset.
- The dataset appears internally consistent after preprocessing and is suitable for further analysis.

---

## Next Steps

- Analyze hourly trends at station and line levels.
- Identify peak-hour behaviour.
- Integrate hourly rainfall data.
- Perform rainfall–ridership correlation analysis.
- Engineer predictive features.
- Develop forecasting models.