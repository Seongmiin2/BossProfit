# BOSSPROFIT

식재료 시장가격 예측을 매장 메뉴 수익성 분석과 연결해, 외식 자영업자가 “어떤 재료를 미리 확인하고 어떤 행동을 해야 하는지” 판단할 수 있게 돕는 의사결정 서비스입니다.

> 핵심 원칙: 검증되지 않은 정확도·매출 개선 수치는 화면과 문서에 확정값처럼 노출하지 않습니다.

## 발표 자료

- [BOSSPROFIT.pptx](BOSSPROFIT.pptx)

## 핵심 기능

| 영역 | 구현 내용 | 상태 |
| --- | --- | --- |
| 인증·온보딩 | JWT 로그인/회원가입, 매장 멤버십, 온보딩 상태 관리 | 구현 |
| 매장 데이터 | 재료·메뉴·레시피 CRUD, 본사 납품 재료 구분 | 구현 |
| POS 데이터 | 수원세류점 POS 엑셀 import, 병합셀 처리, 중복 방지 | 구현 |
| 수익성 계산 | 레시피 원가, 홀/포장/배달 채널별 마진, 메뉴 신호등 | 구현 |
| 매출 분석 | 일자별 매출 캘린더, 메뉴별 매출표, 상위 메뉴 추이 | 구현 |
| 시장 예측 | Base → Weather → Residual 단계형 예측 엔진 | 구현 |
| ML 예측 | 장기 horizon용 글로벌 LightGBM 분위 모델, 통계 모델 폴백 | 구현 |
| 추천 | 예측 변동률 기반 BUY/WATCH/AVOID 구매 권고 | 구현 |
| 생성형 AI | 매장 데이터 기반 “사장님 119” Q&A, 리포트 요약 | 구현 |
| RAG/pgvector | 시장 주간 문서 검색 구조 | 설계·일부 |
| 배포 | 로컬 실행(Django + Vite) | 미배포 |

## 서비스 흐름

```text
시장 가격 데이터 수집
  → 품목별 가격 예측
  → 내 매장 재료·레시피와 연결
  → 메뉴 원가/마진 영향 계산
  → 구매 권고와 행동계획 저장
```

## 예측·추천 구조

최종 예측값은 하나의 블랙박스가 아니라 단계별 성분으로 저장합니다.

```text
final_prediction
= base_prediction
+ weather_adjustment
+ residual_adjustment
```

| 단계 | 모델/방식 | 설명 |
| --- | --- | --- |
| Base | `BasePriceModel` | 최근 가격의 감쇠 로그추세 + 요일 계절성 기반 통계 baseline |
| Weather/Supply | `WeatherSupplyImpactModel` | 주산지 기상 노출 feature의 학습 보정값이 있을 때만 반영, 없으면 0 |
| LightGBM | 글로벌 분위 모델 | 장기 horizon에서 `log(p_t+h / p_t)`를 예측하는 LightGBM quantile 모델 |
| Residual | `ResidualCorrectionModel` | rolling-origin OOF 잔차 평균을 표본 수 기반 shrinkage로 보정 |
| Interval | `IntervalCalibration` | OOF 오차 또는 LightGBM quantile/conformal 보정으로 예측구간 산출 |

단기 horizon은 통계 모델 또는 last-value 기준선이 우선이며, LightGBM 아티팩트가 없거나 적용 조건을 만족하지 않으면 자동 폴백합니다.

추천은 예측 변동률을 행동 언어로 변환합니다.

| 예상 변동률 | 추천 |
| --- | --- |
| `≥ +3%` | BUY: 미리 구매 검토 |
| `-3% ~ +3%` | WATCH: 관망 |
| `≤ -3%` | AVOID: 구매 보류 |

## 데이터베이스 구성

Django ORM 기반 관계형 DB를 사용합니다. 개발 환경은 SQLite이며, 서비스 내부에서는 ORM과 계산 서비스로 데이터를 조회·계산합니다.

주요 데이터 그룹:

- 매장 데이터: `Store`, `Ingredient`, `Menu`, `RecipeItem`, `DailyMenuSale`, `ActionPlan`
- 수익성 데이터: `ProfitAssumption`, `MenuProfitSnapshot`, `PurchasePriceObservation`
- 시장 데이터: `MarketItem`, `MarketPriceObservation`, `WholesaleAuctionObservation`
- 기상·수급 데이터: `WeatherObservation`, `WeatherForecastSnapshot`, `WeatherExposureFeature`, `ProductionStatistic`
- 예측·평가 데이터: `ForecastRun`, `ForecastPoint`, `ForecastComponent`, `MarketForecast`, `OutOfFoldForecast`, `ResidualObservation`, `ForecastCalibration`, `MarketModelMetric`
- 수집 lineage: `IngestionRun`, `RawSourcePayload`

전체 모델 정의:

- [bossprofit/profit/models.py](bossprofit/profit/models.py)
- [bossprofit/accounts/models.py](bossprofit/accounts/models.py)

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| Frontend | Vue 3, Vite, Pinia, Vue Router, Chart.js, Bootstrap, Axios |
| Backend | Django 5, Django REST Framework, SimpleJWT, django-cors-headers |
| DB | SQLite(개발), Django ORM |
| Data/ML | openpyxl, LightGBM, scikit-learn, 자체 통계 예측 엔진 |
| AI | OpenAI SDK 호환 API, GMS gateway 지원, 규칙 기반 fallback |
| Test | Django test, Playwright |

## 실행 방법

### Backend

```bash
cd bossprofit
python manage.py migrate
python manage.py loaddata bootstrap
python manage.py runserver 127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

접속:

- Frontend: <http://127.0.0.1:5173/>
- API: <http://127.0.0.1:8000/api/v1/>

## 주요 명령

```bash
# POS 엑셀 적재
python manage.py import_store_sales_xlsx "<엑셀파일>" \
  --username <사용자명> --store-name "<매장명>" --region "<지역>"

# 시장·기상 데이터 수집
python manage.py ingest_kamis_daily
python manage.py ingest_kamis_period
python manage.py ingest_wholesale_auctions
python manage.py ingest_kma_asos
python manage.py ingest_kma_short_forecast
python manage.py ingest_kma_mid_forecast
python manage.py build_weather_exposures

# 예측·평가·추천
python manage.py train_lightgbm_forecast
python manage.py run_market_forecast
python manage.py backtest_market_forecast
python manage.py backtest_lightgbm
python manage.py rebuild_market_rankings
```

수집 환경변수와 상세 설명은 [bossprofit/DATA_PIPELINE.md](bossprofit/DATA_PIPELINE.md)를 참고하세요.

## 검증

```bash
cd bossprofit
python manage.py test
python manage.py makemigrations --check --dry-run

cd ../frontend
npm run build
npx playwright test
```

## 실행 화면

| 화면 | 데스크톱 | 모바일 |
| --- | --- | --- |
| 랜딩 | ![landing-desktop](artifacts/ui/landing-desktop.png) | ![landing-mobile](artifacts/ui/landing-mobile.png) |
| 대시보드 | ![dashboard-desktop](artifacts/ui/dashboard-desktop.png) | ![dashboard-mobile](artifacts/ui/dashboard-mobile.png) |
| 메뉴·수익성 | ![menus-desktop](artifacts/ui/menus-desktop.png) | ![menus-mobile](artifacts/ui/menus-mobile.png) |
| 분석 리포트 | ![report-desktop](artifacts/ui/report-desktop.png) | ![report-mobile](artifacts/ui/report-mobile.png) |
| 시장 상세 | ![market-desktop](artifacts/ui/market-desktop.png) | ![market-mobile](artifacts/ui/market-mobile.png) |

## 참고 문서

- [BOSSPROFIT_DEVELOPMENT_PLAN.md](BOSSPROFIT_DEVELOPMENT_PLAN.md)
- [BOSSPROFIT_MASTER_REPORT.md](BOSSPROFIT_MASTER_REPORT.md)
- [bossprofit/DATA_PIPELINE.md](bossprofit/DATA_PIPELINE.md)
- [bossprofit/SETUP.md](bossprofit/SETUP.md)
- [AGENTS.md](AGENTS.md)
