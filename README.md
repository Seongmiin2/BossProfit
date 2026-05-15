# BOSSPROFIT — 2026.05.15 작업 로그

소규모 외식 자영업자를 위한 메뉴 단위 수익성 분석 서비스. 오늘 한 작업은 두 가지: **시장조사 보고서**와 **1주차 Django MVP**.

---

## 1. 시장조사 보고서

> 산출물: `bossprofit_market_research.html` (인터랙티브 HTML, Chart.js 기반)

### 핵심 진단

| 지표 | 수치 | 출처 |
|---|---|---|
| 2024년 개인사업자 폐업 | 사상 첫 **100.8만 명** 돌파 | 국세청 |
| 소매·음식업 폐업률 | **20.2%** (전체 평균의 2배) | 국세청 |
| 외식업 영업이익률 | 12.1%(2020) → **8.7%**(2024) | 농식품부·KREI |
| 식재료비 비중 | 36.3% → **40.7%** | 농식품부·KREI |
| 자영업자 1순위 경영 부담 | **원자재·재료비 22.4%** | 한경협 |
| 3년 내 폐업 고려 비율 | **43.6%** | 한경협 |

### 경쟁사 매트릭스

| 서비스 | 핵심 가치 | 메뉴 단위 원가 | 메뉴 엔지니어링 |
|---|---|---|---|
| 캐시노트 (KCD, 140만 사업장) | 카드 매출 정산·고객 분석 | ❌ | ❌ |
| 도도카트 (스포카) | 식자재 OCR·비용 분석 | △ | ❌ |
| 그랜터 | 자동 회계·손익계산서 | ❌ | ❌ |
| 앳트래커 | 기업형 매출·메뉴 분석 | ✓ | ✓ (B2B only) |
| **BOSSPROFIT** | **메뉴별 수익성·신호등** | ✓ | ✓ |

→ **시장 사각지대**: 자영업자가 쓸 수 있는 "메뉴 단위 수익성 분석"은 비어있다.

### 포지셔닝 결정

학술 용어(Star/Plowhorse/Puzzle/Dog) → **사장님 언어**로 변환:

- 🟢 **간판 메뉴** — 더 밀어라
- 🟡 **손해 보는 베스트셀러** — 가격 ↑ 또는 원가 ↓
- 🟡 **숨은 효자** — 사진·이름·위치 개선
- 🔴 **메뉴판 정리 대상**
- 🔴 **배달 손실** — 단품 배달 적자 (묶음/최소주문 정책 필요)

### TAM/SAM/SOM

| | 정의 | 규모 |
|---|---|---|
| TAM | 전국 음식점·주점·카페 | 약 80만 곳 |
| SAM | 메뉴 30개 이하·POS 사용 소규모 F&B | 약 35만 곳 |
| SOM | 수도권 카페·소규모 한식·분식 (1년) | 5,000 곳 |

월 9,900원 기준 SOM 10% 점유 → ARR ≈ 5,940만원.

### 확인된 주요 리스크

1. **POS 직접 연동 없으면** 자동화 약속이 깨짐 → 수기 입력 회귀
2. **OCR 5% 오류**도 사장님은 신뢰 안 함 → 정확도 임계점 높음
3. **캐시노트가 후행 출시** 가능성 → 해자(moat) 정의 필요

---

## 2. Django 1주차 MVP

> 산출물: `bossprofit_django_week1.zip` (실행 가능한 Django 프로젝트)

엑셀 계산기(`BOSSPROFIT_1주차_MVP_최종계산기.xlsx`)를 Django로 그대로 이식. 21개 메뉴 + 35개 재료 + 118개 레시피 데이터 포함.

### 검증 결과 (엑셀 ↔ Django 완전 일치)

| KPI | 엑셀 | Django |
|---|---|---|
| 총 월매출 | 4,985,300원 | 4,985,300원 ✓ |
| 월 예상이익 | 2,037,333원 | 2,037,334원 ✓ (반올림 1원차) |
| 총 월주문수 | 492건 | 492건 ✓ |
| 평균 원가율 | 37.8% | 37.8% ✓ |
| 평균 판매량 | 23.4건 | 23.4건 ✓ |
| 배달 손실 메뉴 | 13개 | 13개 ✓ |

### 프로젝트 구조

```
bossprofit/
├── manage.py
├── requirements.txt
├── seed_data.json                  # 21메뉴 + 35재료 + 118레시피
├── SETUP.md
├── bossprofit_project/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── profit/
    ├── models.py                   # 5개 모델
    ├── calculator.py               # 수익성 계산 + 신호등 분류
    ├── views.py                    # 대시보드 / 메뉴 / 상세
    ├── urls.py
    ├── admin.py
    ├── management/commands/
    │   └── seed_data.py            # JSON → DB 적재 + 재계산
    ├── static/profit/
    │   └── styles.css              # 자체 CSS (CDN 의존 없음)
    └── templates/profit/
        ├── base.html
        ├── dashboard.html
        ├── menu_list.html
        └── menu_detail.html
```

### 5개 모델

| 모델 | 역할 |
|---|---|
| `Ingredient` | 식자재 마스터 (구매 단위 + 가격) → `unit_cost`는 property로 자동 계산 |
| `Menu` | 판매 메뉴 (이름, 카테고리, 가격, 월 판매량, 포장비) |
| `RecipeItem` | 메뉴 × 재료 + 사용량 |
| `ProfitAssumption` | 매장 단위 가정 (홀/배달/포장 비중, 수수료 등) |
| `MenuProfitSnapshot` | 계산 결과 캐싱 (시계열 보존) |

### 3개 화면

| URL | 화면 |
|---|---|
| `/` | KPI 6개 + 핵심 인사이트 4개 + 메뉴 신호등 테이블 |
| `/menus/` | 21개 메뉴 카드 그리드 |
| `/menus/<menu_id>/` | 홀·포장·배달 마진 + 레시피 분해 (원가 비중 막대) |
| `/admin/` | Django 관리자 (재료, 메뉴, 가정 직접 편집) |
| `POST /recalculate/` | 헤더 "⟳ 재계산" 버튼 |

### 신호등 분류 로직

```python
if 배달마진 < 0 and 가중마진 < 0:
    return "🔴 배달 손실"

if 월판매 >= 평균 and 원가율 <= 35%:  return "🟢 간판 메뉴"
if 월판매 >= 평균 and 원가율 >  35%:  return "🟡 손해 보는 베스트셀러"
if 월판매 <  평균 and 원가율 <= 35%:  return "🟡 숨은 효자"
else:                                return "🔴 정리 검토"
```

평균 판매량 = 활성 메뉴 전체의 `monthly_orders` 평균 (현재 23.4건/월).

### 실행 방법

```bash
unzip bossprofit_django_week1.zip && cd bossprofit
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

브라우저에서 `http://127.0.0.1:8000` 접속.

### 데이터 변경 흐름

1. 식자재 가격 변경 → `/admin/profit/ingredient/`
2. 메뉴 가격/판매량 변경 → `/admin/profit/menu/`
3. 가정 변경 (배달 비중 등) → `/admin/profit/profitassumption/`
4. 대시보드 헤더의 **⟳ 재계산** 클릭 → `MenuProfitSnapshot` 새로 생성

---

## 3. 의도적으로 단순화한 부분 (다음 작업 후보)

- [ ] 사용자 인증 + 매장별 멀티테넌트
- [ ] 사장님용 입력 폼 (admin 화면이 아닌 모바일 친화 UI)
- [ ] 영수증 OCR 업로드 (CLOVA OCR vs Google Vision API PoC)
- [ ] KAMIS Open API 시세 자동 반영 (cron / Celery)
- [ ] 시계열 차트 (Chart.js로 월별 이익 추이)
- [ ] 사장님 5명 인터뷰 (시장조사 보고서 마지막 체크리스트)

---

## 4. 오늘 산출 파일 정리

```
bossprofit_market_research.html        시장조사 인터랙티브 보고서
bossprofit_django_week1.zip            Django MVP 프로젝트 전체
bossprofit_dashboard.png               대시보드 스크린샷
bossprofit_menu_detail.png             메뉴 상세 스크린샷
README.md                              이 파일
```

---

*작성일: 2026.05.15 
