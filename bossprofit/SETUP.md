# BOSSPROFIT 1주차 Django MVP

엑셀 계산기를 Django로 그대로 옮긴 1주차 산출물.

## 빠른 실행 (5줄)

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

브라우저에서 `http://127.0.0.1:8000` 접속.

## 구조

```
bossprofit/
├── manage.py
├── seed_data.json                  # 21개 메뉴 + 35개 재료 + 118개 레시피
├── requirements.txt
├── bossprofit_project/             # Django 프로젝트 설정
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── profit/                         # 메인 앱
    ├── models.py                   # 5개 모델
    ├── calculator.py               # 수익성 계산 + 신호등 분류
    ├── views.py                    # 대시보드 / 메뉴 / 상세
    ├── urls.py
    ├── admin.py                    # Django Admin 등록
    ├── management/commands/
    │   └── seed_data.py            # JSON → DB
    └── templates/profit/
        ├── base.html
        ├── dashboard.html          # preview 이미지와 동일
        ├── menu_list.html
        └── menu_detail.html
```

## 핵심 화면

| URL | 화면 |
|---|---|
| `/` | KPI 6개 + 핵심 인사이트 4개 + 메뉴 신호등 테이블 |
| `/menus/` | 21개 메뉴 카드 그리드 |
| `/menus/M001/` | 메뉴 상세 (홀·포장·배달 마진 + 레시피 분해) |
| `/admin/` | 모델 직접 편집 (재료, 메뉴, 가정) |
| `POST /recalculate/` | 헤더의 "⟳ 재계산" 버튼 |

## 데이터 변경 흐름

1. 식자재 가격 변경 → `/admin/profit/ingredient/`
2. 메뉴 가격/판매량 변경 → `/admin/profit/menu/`
3. 가정 변경 (배달 비중 등) → `/admin/profit/profitassumption/`
4. 대시보드에서 **⟳ 재계산** 버튼 클릭 → `MenuProfitSnapshot` 갱신

## 신호등 분류 로직

```python
if 배달마진 < 0 and 가중마진 < 0:  # 배달 판매가 적자
    return "🔴 배달 손실"

if 월판매 >= 평균 and 원가율 <= 35%:  return "🟢 간판 메뉴"
if 월판매 >= 평균 and 원가율 >  35%:  return "🟡 손해 보는 베스트셀러"
if 월판매 <  평균 and 원가율 <= 35%:  return "🟡 숨은 효자"
else:                                return "🔴 정리 검토"
```

평균 판매량 = 활성 메뉴 전체의 monthly_orders 평균 (현재 데이터: 23.4건/월)

## 2주차에 추가할 것

- [ ] 영수증 OCR 업로드 (CLOVA OCR or Vision API)
- [ ] KAMIS 시세 자동 반영 (cron + Celery)
- [ ] 메뉴/재료 입력 폼 (관리자 화면 말고 사장님용 UI)
- [ ] 시계열 차트 (Chart.js로 월별 이익 추이)
- [ ] 사용자 인증 + 매장별 멀티테넌트
