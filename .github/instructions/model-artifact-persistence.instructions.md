---
description: "Use for any forecasting or machine-learning workflow in project notebooks. Require persisted fitted models, preprocessing, ordered feature schemas, training/validation metadata, and fresh-process reload checks before predictions are accepted."
applyTo: "Notebooks/**/*.ipynb"
---
# Model Artifact Persistence

For every future model-training workflow in this project:

- Persist each validation-selected fitted estimator together with its complete preprocessing pipeline using `joblib` under `Models/`.
- Save a manifest with artifact filenames, ordered feature names, target, estimator parameters, training data and split, validation selection criterion/results, and Python/library versions.
- Keep model selection and preprocessing fit within training/validation data; never use test results to select a model.
- Before accepting or publishing predictions, load every artifact in a fresh Python process, verify its feature schema against the manifest, and compare predictions on identical inputs with the in-memory fitted object using a documented numerical tolerance.
- Fail explicitly if persistence, reload, schema checks, or prediction equivalence fail. Never silently continue with predictions when the fitted model cannot be recovered.
