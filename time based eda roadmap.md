# Time-Based EDA Roadmap

**Notebook:** `03_Time_Based_EDA.ipynb`

---

# Objective

The primary objective of this notebook is to understand **how Delhi Metro ridership changes over time** before integrating weather data.

Unlike the previous EDA, which focused on **where passengers travel**, this notebook focuses on **when passengers travel**.

Understanding these temporal patterns is essential before building any forecasting model.

---

# Recommended Workflow

## Phase 1 — Overall Hourly Ridership

### Question 1 ⭐⭐⭐⭐⭐
## How does total metro ridership vary throughout the day?

**Goal**

Understand the overall daily ridership pattern.

**Visualisation**

- Line Chart
- X-axis: Hour (0–23)
- Y-axis: Total (or Average) Ridership

**Questions to Answer**

- When does ridership begin increasing?
- When is the morning peak?
- When is the evening peak?
- Which peak is larger?
- Is there a noticeable afternoon lull?
- When does ridership begin declining?
- Which hours have the lowest demand?

**Expected Outcome**

This should become one of the most important figures in the research paper.

---

### Question 2 ⭐⭐⭐⭐
## How much does each hour contribute to total daily ridership?

Instead of plotting raw passenger counts, calculate each hour's percentage contribution to the day's total.

**Questions to Answer**

- Which three hours contribute the most ridership?
- What percentage of passengers travel during peak hours?
- How concentrated is passenger demand?

---

### Question 3 ⭐⭐⭐
## What is the hour-to-hour rate of change in ridership?

Calculate:

```
Ridership(Current Hour)
-
Ridership(Previous Hour)
```

**Questions to Answer**

- Which hour experiences the fastest increase?
- Which hour experiences the steepest decline?
- Where does commuter demand change most rapidly?

---

# Phase 2 — Entry vs Exit Analysis

### Question 4 ⭐⭐⭐⭐⭐
## How do Entry and Exit ridership vary throughout the day?

**Visualisation**

Two-line chart

- Entry
- Exit

**Questions to Answer**

- When do Entries peak?
- When do Exits peak?
- Do they peak at the same time?
- Which dominates during the morning?
- Which dominates during the evening?

---

### Question 5 ⭐⭐⭐⭐
## What is the Entry-to-Exit ratio throughout the day?

Calculate:

```
Entry / Exit
```

for every hour.

**Questions to Answer**

- Which hours have more Entries?
- Which hours have more Exits?
- Which hours are nearly balanced?

---

### Question 6 ⭐⭐⭐⭐
## What is the hourly difference between Entry and Exit ridership?

Calculate:

```
Entry - Exit
```

for every hour.

**Questions to Answer**

- Which hour has the largest imbalance?
- Does the morning differ from the evening?
- Is the imbalance consistent throughout the day?

---

# Phase 3 — Business Day Analysis

### Question 7 ⭐⭐⭐⭐⭐
## How does hourly ridership differ between Business Days and Non-Business Days?

**Visualisation**

Two-line chart

- Business Day
- Non-Business Day

**Questions to Answer**

- How much does total demand decrease?
- Does the morning peak flatten?
- Does the evening peak change?

---

### Question 8 ⭐⭐⭐⭐
## How do Entry and Exit patterns differ between Business Days and Non-Business Days?

**Visualisation**

Four-line chart

Business Day
- Entry
- Exit

Non-Business Day
- Entry
- Exit

**Questions to Answer**

- Does commuting behaviour change?
- Are weekends more balanced?
- Which direction changes the most?

---

# Phase 4 — Monthly Time Behaviour

### Question 9 ⭐⭐⭐⭐
## How does the hourly ridership curve vary across different months?

**Questions to Answer**

- Are peak hours consistent?
- Which month has the highest demand?
- Do some months exhibit different travel behaviour?

---

### Question 10 ⭐⭐⭐
## How do morning and evening peaks compare across months?

Instead of comparing the full hourly curve, compare only the peak values.

**Questions to Answer**

- Does the peak hour shift?
- Does peak intensity change across months?

---

# Phase 5 — Variability Analysis

### Question 11 ⭐⭐⭐⭐
## Which hours exhibit the highest variability?

Calculate the standard deviation of ridership for each hour.

**Questions to Answer**

- Which hours are most variable?
- Which hours are the most stable?

---

### Question 12 ⭐⭐⭐
## Which hours are relatively the most unpredictable?

Calculate the coefficient of variation:

```
Standard Deviation
------------------
Mean Ridership
```

**Questions to Answer**

- Which hours have the greatest relative variability?
- Which hours would be hardest to forecast?

---

# Phase 6 — Forecasting Preparation

### Question 13 ⭐⭐⭐⭐
## Which hours contribute the largest share of total daily ridership?

Calculate the percentage contribution of every hour.

**Questions to Answer**

- Which hours dominate the network?
- Which hours should forecasting prioritize?

---

### Question 14 ⭐⭐⭐⭐
## Which hours are most important for forecasting?

Identify the hours that simultaneously have:

- High passenger volume
- High variability

These hours will likely be the most valuable targets for predictive modelling.

---

# Current Progress

| Phase | Status |
|--------|--------|
| Basic EDA | ✅ Completed |
| Data Validation | ✅ Completed |
| Top Stations | ✅ Completed |
| Top Metro Lines | ✅ Completed |
| Entry vs Exit by Line | ✅ Completed |
| Time-Based EDA | ⏳ Not Started |
| Weather Integration | ⏳ Pending |
| Feature Engineering | ⏳ Pending |
| Forecasting Models | ⏳ Pending |

---

# Tomorrow's Plan

Focus only on the first four analyses.

1. Overall Hourly Ridership ⭐⭐⭐⭐⭐
2. Hourly Entry vs Exit ⭐⭐⭐⭐⭐
3. Business Day vs Non-Business Day ⭐⭐⭐⭐
4. Entry–Exit Difference / Ratio ⭐⭐⭐⭐

Do not move to monthly or weather analysis until these four questions are fully explored and documented.