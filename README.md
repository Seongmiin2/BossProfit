# BOSSPROFIT

식재료 시장가격을 예측하고, 가격 변화가 내 매장의 어떤 메뉴에 영향을 주는지
확인한 뒤 대응 행동까지 정리하는 외식 자영업자용 의사결정 서비스입니다.

> 어떤 재료의 가격이 오르고, 내 매장의 어떤 메뉴를 먼저 확인해야 하는지 알려주는 서비스

현재 구현은 Vue 3 프런트엔드와 Django REST API를 사용합니다. 매장 판매 데이터,
KAMIS 가격, 도매시장 거래, 주산지 기상 데이터를 한 파이프라인에서 다루며,
데이터가 부족한 경우 수익성이나 운영 성과를 임의로 단정하지 않습니다.

## 핵심 흐름

1. 시장가격 예측
2. 내 메뉴 영향 계산
3. 근거 기반 행동 전략 제안

로그인 후 대시보드에서는 가장 위험한 재료와 예측구간을 먼저 보여줍니다.
메뉴 화면은 실제 POS 판매량과 매출을 표시하되, 레시피와 원가가 연결되지 않은
메뉴는 `분석 대기`로 분리합니다.

## 기술 구성

```text
frontend/                  Vue 3 + Vite + Pinia
bossprofit/                Django + Django REST Framework + SQLite
  accounts/                인증과 매장 멤버십
  profit/                  판매·메뉴·시장·기상·예측·분석
  profit/forecasting/      단계형 예측 엔진과 평가 도구
```

예측값은 다음 구성요소를 분리해 저장합니다.

```text
final_prediction
= base_prediction
+ weather_adjustment
+ residual_adjustment
```

- `BasePriceModel`: 가격 이력과 계절·추세
- `WeatherSupplyImpactModel`: 주산지 기상·수급 노출
- `ResidualCorrectionModel`: rolling-origin OOF 잔차
- `IntervalCalibration`: 품목·예측기간별 구간 보정

평가는 마지막 값 및 계절 나이브 baseline과 비교하며 WAPE, MASE, MAE, RMSE,
bias, pinball loss, interval coverage를 기록합니다. 검증되지 않은 정확도나
매출 개선 수치는 제품 화면에 노출하지 않습니다.

## 로컬 실행

### 백엔드

```powershell
cd bossprofit
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

### 프런트엔드

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

- 프런트엔드: <http://127.0.0.1:5173/>
- API: <http://127.0.0.1:8000/api/v1/>

API 키는 커밋하지 않고 `bossprofit/.env`에만 저장합니다. 필요한 환경변수와
실데이터 수집 명령은 [bossprofit/DATA_PIPELINE.md](bossprofit/DATA_PIPELINE.md)를
참고하세요.

## 매장 POS 데이터

수원세류점 POS 엑셀은 상품군 병합 셀을 올바르게 이어받아 파싱합니다. 동일한
상품·날짜가 여러 파일에 있으면 합산하며, 누락된 날짜를 판매량 0으로 만들지
않습니다.

```powershell
cd bossprofit
..\.venv\Scripts\python.exe manage.py import_pos_sales `
  --username <사용자명> `
  --store-name "<매장명>" `
  --file "<엑셀1>" `
  --file "<엑셀2>"
```

## 주요 API

- `GET /api/v1/public/product-preview/`
- `GET /api/v1/dashboard/`
- `GET /api/v1/analysis/store/`
- `GET /api/v1/analysis/report/`
- `POST /api/v1/analysis/follow-up/`
- `POST /api/v1/action-plans/`
- `GET /api/v1/market/rankings/`

매장 소유 데이터는 인증된 사용자의 `store_id` 범위에서만 조회합니다.

## 검증

```powershell
cd bossprofit
..\.venv\Scripts\python.exe manage.py test
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run

cd ..\frontend
npm run build
npx playwright test
```

상세 제품·모델 요구사항은
[BOSSPROFIT_DEVELOPMENT_PLAN.md](BOSSPROFIT_DEVELOPMENT_PLAN.md),
전체 설계 맥락은 [BOSSPROFIT_MASTER_REPORT.md](BOSSPROFIT_MASTER_REPORT.md)를
참고하세요.
