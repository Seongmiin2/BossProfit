# BOSSPROFIT Codex Development Rules

## 1. Source of Truth

- Read this file before making any change.
- Use `BOSSPROFIT_DEVELOPMENT_PLAN.md` as the detailed product and engineering specification.
- Use the presentation proposal only for product narrative and business context. Do not treat presentation targets or example numbers as measured model results.
- When documentation and code disagree, inspect the current implementation and report the conflict before changing behavior.

## 2. Product Boundary

- BOSSPROFIT is not a general-purpose ERP.
- Build only the data and workflows required for:
  - ingredient purchase-price tracking;
  - menu and recipe costing;
  - sales and profitability analysis;
  - agricultural price forecasting;
  - store-specific impact simulation;
  - evidence-based action plans.
- Do not add tax filing, payroll, attendance, electronic approval, complex WMS, automatic ordering, or broad POS integrations unless explicitly requested.

## 3. Forecasting Architecture

Implement the forecasting system as independently measurable stages:

1. `BasePriceModel`
   - Learns price history, seasonality, auction price, and volume patterns.
2. `WeatherSupplyImpactModel`
   - Learns production-region weather exposure and supply shocks.
3. `ResidualCorrectionModel`
   - Learns errors from rolling-origin out-of-fold predictions only.
4. `IntervalCalibration`
   - Calibrates prediction intervals by item and forecast horizon.

The final prediction must preserve every component:

```text
final_prediction
= base_prediction
+ weather_adjustment
+ residual_adjustment
```

Persist and expose each component separately.

## 4. No-Leakage Rules

- Never use a random train/test split for time-series evaluation.
- Never use future actual prices as features.
- Never use future observed weather as if it were an available forecast.
- Preserve `issued_at`, `valid_at`, and `collected_at` for weather forecasts and external data.
- Build every feature with point-in-time correctness.
- Generate residual labels from rolling-origin OOF predictions, not in-sample fitted values.
- Keep residual labels separate for 1-day, 7-day, and 30-day horizons unless horizon is an explicit model feature.
- Fit scalers, encoders, imputers, feature selection, and calibration using training data only.
- Report oracle-weather experiments separately. Never present them as deployable performance.

## 5. Weather and Supply Data

- Use the weather of production regions, not the weather of the wholesale market or restaurant.
- Maintain versioned mappings among:
  - market item;
  - crop and variety;
  - production region and regional weight;
  - growth stage;
  - weather station or forecast grid.
- Support weather exposure windows of 3, 7, 14, 30, 60, and 90 days where data permits.
- Candidate weather variables include temperature, rainfall, humidity, solar radiation, sunshine, wind, soil temperature, soil moisture, heatwave, frost, drought, heavy rain, typhoon, and growing degree days.
- Treat wholesale auction volume, arrivals, acreage, yield, production, disease, and agricultural outlook data as supply variables.
- Do not silently force uncertain item, region, station, or unit mappings. Store mapping confidence and review status.

## 6. Model Evaluation

Always compare:

1. last-value baseline;
2. seasonal-naive baseline;
3. base price model;
4. base plus weather and supply adjustment;
5. base plus weather, supply, and residual correction.

Evaluate each item and horizon with:

- WAPE;
- MASE;
- MAE or RMSE;
- bias;
- pinball loss;
- interval coverage;
- interval width.

Required analysis:

- rolling-origin backtest;
- normal periods versus weather-shock periods;
- ablation by model stage;
- residual mean and autocorrelation;
- paired bootstrap confidence interval or Diebold-Mariano test where appropriate.

Do not claim that a complex model is better without an untouched test result. If a correction stage degrades validation or test performance for an item and horizon, disable that correction and record the reason.

## 7. Data and Reproducibility

- Store raw source payloads or immutable source references.
- Every dataset build must record:
  - source versions;
  - observation cutoff;
  - feature definition version;
  - item and region mappings;
  - code revision;
  - random seed where applicable.
- The same snapshot and code revision must reproduce the same training dataset.
- Use migrations for schema changes.
- Use Decimal or integer KRW for money.
- Standard units are `g`, `ml`, and `ea`.
- Keep lineage from final forecast to source observations and model versions.

## 8. Multi-Tenant Security

- Every store-owned entity must be scoped by `store_id`.
- Enforce store scope in queries, services, permissions, and tests.
- Always create at least two stores in authorization tests.
- Never expose another store's raw data, chat history, tool output, forecast impact, or action plan.
- LLMs must call allowlisted tools and must not execute arbitrary SQL.
- Write operations require explicit user confirmation.

## 9. Engineering Style

- Read the repository before choosing frameworks or abstractions.
- Follow existing project patterns unless they prevent correctness.
- Keep views and controllers thin.
- Put costing, forecasting, scenario, and orchestration logic in testable services.
- Prefer typed schemas and structured parsers over ad hoc string handling.
- Keep changes scoped to the requested feature.
- Do not delete or overwrite unrelated user changes.
- Do not hardcode secrets, API keys, model IDs, or local machine paths.

## 10. Testing and Completion

For every implementation:

1. state the affected requirements;
2. inspect existing code and tests;
3. implement the smallest complete change;
4. add or update tests;
5. run relevant tests;
6. report results and remaining limitations.

Forecasting work is not complete until:

- point-in-time and leakage tests pass;
- rolling-origin OOF predictions are persisted;
- component predictions are reproducible;
- baseline and ablation results are generated;
- failed ingestion and model runs are observable;
- documentation is updated.

## 11. Prohibited Claims

- Do not invent model accuracy, improvement percentages, revenue impact, or user outcomes.
- Do not present validation performance as test performance.
- Do not present overseas or synthetic datasets as Korean operational evidence.
- Do not describe a prototype as a production service.
- Mark targets as targets and measured results as measured results.

