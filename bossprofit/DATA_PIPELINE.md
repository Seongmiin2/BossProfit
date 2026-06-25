# BOSSPROFIT data pipeline

## Local secrets

Copy `.env.example` to `.env`. The real `.env` is ignored by Git.

Required variables:

- `KAMIS_CERT_ID`
- `KAMIS_CERT_KEY`
- `DATA_GO_KR_SERVICE_KEY`

Never put service keys in source code, migrations, fixtures, screenshots, or commits.

## Store POS import

```powershell
python manage.py import_store_sales_xlsx `
  ..\수원세류점1.xlsx ..\수원세류점2.xlsx `
  --username ksm960mm `
  --store-name "한신우동 수원세류점" `
  --region "경기 수원시 권선구" `
  --replace-sales
```

The importer:

- hashes every source file for idempotency;
- keeps import status and row counts;
- carries merged product cells forward;
- stores quantity, gross revenue, discount, and net revenue;
- scopes every row to the user's store.

Real POS exports are excluded from Git.

## Market price ingestion

Latest comparison board:

```powershell
python manage.py ingest_kamis_daily --date 2026-06-24 --category-code 200
```

Continuous daily series for forecasting:

```powershell
python manage.py ingest_kamis_period `
  --start-date 2026-01-01 --end-date 2026-06-24 `
  --category-code 200 --item-code 245 --kind-code 00 --rank-code 04
```

Every run stores:

- status and counts in `IngestionRun`;
- a redacted request;
- the immutable raw response;
- normalized observations with source lineage.

## Weather ingestion

```powershell
python manage.py ingest_kma_asos `
  --station-id 119 --start-date 2026-06-20 --end-date 2026-06-24

python manage.py ingest_kma_short_forecast `
  --base-date 2026-06-25 --base-time 0500 --nx 60 --ny 121

python manage.py ingest_kma_mid_forecast `
  --region-id 11B00000 --issued-at 2026-06-25T06:00

python manage.py ingest_agri_crop_weather `
  --item-code KAMIS:245:00:04 --crop-code 120100 `
  --start-date 2026-03-26 --end-date 2026-06-24

python manage.py build_weather_exposures `
  --item-code KAMIS:245:00:04 --date 2026-06-24

python manage.py ingest_wholesale_auctions `
  --date 2026-06-24 --pages 1 --rows 1000
```

The Suwon examples only validate connectivity. Crop forecasts must use reviewed
production-region mappings, not restaurant weather.

## Forecasting

Rolling-origin OOF only:

```powershell
python manage.py backtest_market_forecast `
  --item-code KAMIS:245:00:04 --horizons 1,7,30
```

Operational forecast:

```powershell
python manage.py run_market_forecast `
  --item-code KAMIS:245:00:04 `
  --date 2026-06-24 --horizons 1,7,30,60,90
```

The persisted identity is:

```text
final_prediction
= base_prediction
+ weather_adjustment
+ residual_adjustment
```

Weather adjustment remains disabled until reviewed production-region exposure
features and trained adjustment output exist. Residual correction remains
disabled until at least eight rolling-origin OOF residuals exist. Metrics are
marked verified only when at least 30 OOF evaluations exist.

## Current external-source state

- KAMIS latest and period price APIs: connected.
- KMA ASOS daily: connected.
- KMA short forecast: connected.
- KMA mid forecast: connected.
- RDA production-region agricultural weather: connected; mappings remain pending review.
- Public wholesale auction feed: connected.
- RDA institution agricultural detailed weather: the supplied portal key currently
  receives HTTP 403 on dataset `15073274`; verify that dataset-specific utilization
  approval is active before enabling its adapter.
