# BOSSPROFIT 개발 실행 기획서

> 매장 데이터와 시장 가격을 연결해, 가격 변동을 미리 준비하고 위기 대응 전략의 실행 결과까지 추적하는 AI 미니 ERP

문서 버전: v1.0  
기준일: 2026-06-24  
개발 기준: 4개 팀, 6주 MVP  
대상: 프론트엔드·UI/UX, 백엔드·API, DB·데이터 엔지니어링, ML·RAG·LLM

---

## 0. 이 문서로 바로 결정할 것

이 기획서는 아이디어 설명서가 아니라 개발 착수 기준서다. 모든 팀은 아래 여섯 가지 결정을 공통 전제로 사용한다.

1. BOSSPROFIT은 범용 ERP가 아니라 메뉴 수익 예측에 필요한 데이터만 연결한 AI 미니 ERP다.
2. MVP의 첫 성공은 사용자가 첫 분석을 만드는 순간이다.
3. 숫자는 SQL·계산 엔진·예측 모델이 만들고, LLM은 근거를 조합해 행동을 제안한다.
4. 정형 가격 행은 PostgreSQL에서 조회하고, 문서·사건·과거 전략은 pgvector에서 검색한다.
5. 가격 예측은 `기본 가격모델 → 기상·수급 영향 보정 → 잔차 보정`의 3단계 파이프라인으로 구성한다.
6. 잔차 모델은 과거 예측에서 발생한 오차만 학습하며, 테스트·운영 시점에 실제 미래 가격이나 실제 미래 날씨를 사용하지 않는다.
7. 첫 운영 품목은 가격·거래량·주산지·기상 데이터 품질을 검증한 5개 이내 대표 품목으로 제한한다.
8. 6주 안에 가입부터 행동계획 저장까지 하나의 완결된 세로 흐름을 출시한다.

### MVP 성공 문장

신규 사용자가 모바일에서 매장을 만들고, 재료와 메뉴를 등록한 뒤, 시장 가격 전망이 자신의 메뉴 원가에 미치는 영향을 확인하고, 자영업 119의 제안을 행동계획으로 저장할 수 있다.

### 이번 MVP에서 만들지 않는 것

- 세무 신고, 회계 전표, 급여, 근태, 전자결재
- 복잡한 창고·재고관리와 자동 발주
- 모든 POS·배달 플랫폼 연동
- 모든 KAMIS 품목의 즉시 예측
- 뉴스 전반을 실시간으로 수집하는 범용 검색 서비스
- 충분한 검증 없이 딥러닝을 적용한 장기 예측
- LLM의 직접 SQL 실행 또는 사용자 확인 없는 쓰기 작업

---

## 1. 문제 정의

### 문제 A. 반복되는 가격 변동을 사전에 준비할 수 없다

식재료 가격은 날씨, 작황, 출하량, 명절 수요, 환율, 유가와 물류비에 따라 변하지만 음식점은 메뉴 가격을 매번 바꿀 수 없다. 소규모 매장은 납품 가격이 오른 뒤에야 손실을 인지하며, 어느 메뉴가 얼마나 영향을 받는지 계산하기도 어렵다.

BOSSPROFIT은 다음 순서로 사후 확인을 사전 준비로 바꾼다.

1. KAMIS 가격과 외부 변수를 매일 수집한다.
2. 품목별 과거 가격·거래량·계절성으로 1차 가격을 예측한다.
3. 주산지의 기온·강수·일사·토양수분·특보와 생육단계를 결합해 기상에 따른 공급 충격과 가격 보정량을 추정한다.
4. 과거 1·2단계 예측과 실제 가격의 차이인 잔차를 학습해 남은 편향을 다시 보정한다.
5. 최종 7일·30일 가격과 예측구간을 사용자의 실제 구매가격, 레시피, 판매량과 연결한다.
6. 영향을 받는 메뉴와 예상 손실을 우선순위로 보여준다.
7. 구매·레시피·구성·판매가격 대안을 비교한다.

### 예측 고도화 의도

가격 이력만으로 다음 값을 맞히는 모델은 폭염, 집중호우, 한파, 태풍과 같은 생산 충격이 가격에 반영되기 전까지 이를 알기 어렵다. BOSSPROFIT은 기상 자체와 가격의 단순 상관관계만 학습하지 않는다.

```text
주산지 기상 노출
→ 생육·수확·출하량 충격
→ 도매시장 거래량과 가격 변화
→ KAMIS 소비·중도매 가격 변화
```

이 인과 순서를 반영해 주산지와 작물 생육단계별 누적 기상 노출을 만들고, 거래량·출하량을 중간 변수로 사용한다. 이후 실제 가격과의 오차를 별도 잔차 모델이 학습한다.

### 문제 B. 갑작스러운 외부 충격에 대응 기준이 없다

국제 분쟁, 수출 제한, 항만 폐쇄, 감염병과 같은 사건은 과거 시계열만으로 정확히 예측하기 어렵다. 중요한 것은 사건을 맞히는 것이 아니라 사건 발생 후 내 매장에 미칠 영향을 빠르게 계산하고 행동 기준을 세우는 것이다.

자영업 119는 관련 문서와 과거 사례를 검색하고, 매장 데이터와 시나리오 계산 결과를 결합해 다음을 제공한다.

- 지금 발생한 일과 신뢰 가능한 근거
- 내 매장의 노출 재료·메뉴·채널
- 예상 손익 범위
- 오늘과 1주 안에 할 일
- 가격 인상 외의 대안
- 성공 기준과 중단 기준
- 점검일이 포함된 행동계획

### 일반 ERP와의 차별점

일반 ERP는 입력한 데이터를 표로 보여준다. BOSSPROFIT은 같은 데이터를 이용해 “양파 구매가격이 시장 평균보다 13% 높다”, “현재 추세가 유지되면 30일 뒤 돈까스 원가가 약 4.8% 오를 가능성이 있다”, “2주 고정가 협상과 세트 구성 변경을 먼저 검토하라”처럼 다음 행동을 제안한다.

---

## 2. 목표 사용자와 사용 조건

### 핵심 사용자

- 음식점을 직접 운영하는 1~5인 소규모 사업자
- 엑셀·회계·데이터 분석 도구 사용이 익숙하지 않은 사용자
- 영업 중 모바일로 1~3분 안에 입력해야 하는 사용자
- 재료비 상승을 체감하지만 메뉴별 영향은 계산하지 못하는 사용자

### 핵심 과업

1. 재료 구매가격을 60초 안에 기록한다.
2. 메뉴와 레시피를 3분 안에 등록한다.
3. 오늘 판매량을 1분 안에 입력한다.
4. 가격 전망이 내 메뉴에 미치는 영향을 한 화면에서 이해한다.
5. 위기 대응 대안을 비교하고 행동계획을 저장한다.

### 제품 언어

전문 용어 대신 사용자가 실제로 말하는 표현을 사용한다.

| 사용하지 않는 표현 | 사용할 표현 |
|---|---|
| 마스터 데이터 | 내 재료 |
| 원가 가정 | 가격이 오르면 |
| 손익 스냅샷 | 이번 달 예상 이익 |
| 시계열 예측 | 가격 전망 |
| ActionPlan | 실행계획 |
| 데이터 CRUD | 추가·수정·삭제 |

---

## 3. MVP 사용자 흐름

### E2E 핵심 흐름

1. 회원가입
2. 매장 등록
3. 첫 재료 등록 및 KAMIS 품목 연결
4. 실제 구매가격 입력
5. 첫 메뉴와 레시피 등록
6. 최근 판매량 입력
7. 첫 원가·손익 분석 생성
8. 재료 가격 전망 확인
9. 내 메뉴 영향 확인
10. 자영업 119에서 대응안 비교
11. 행동계획 저장
12. 점검일에 실제 결과 기록

### 단계 공개 원칙

- 현재 단계만 확장하고 다음 단계는 제목과 진행 상태만 보여준다.
- 저장이 성공해야 다음 단계가 열린다.
- 선택 입력은 핵심 흐름을 막지 않는다.
- 중단한 사용자는 마지막 완료 단계부터 재개한다.
- 완료된 단계는 요약 카드로 축소하고 수정 진입점을 제공한다.

---

## 4. 정보구조와 화면 명세

모바일 하단 내비게이션은 `오늘 | 입력 | 시장 | 119` 네 개로 고정한다. 세부 ERP 관리는 오늘 화면의 설정 진입점에서 제공한다.

### S01. 공개 홈

목표: 제품이 “원가 계산기”가 아니라 “시장 변화에 대비하는 도구”임을 10초 안에 이해시킨다.

핵심 구성:

- H1: 식재료 가격이 오르기 전에, 내 가게가 할 일을 알려드립니다.
- 오늘의 상승 품목 3개
- 전망 예시 1개
- 자영업 119 답변 예시 1개
- Primary CTA: 무료로 시작하기
- Secondary CTA: 시장 가격 보기

완료 조건:

- 첫 화면에 CTA가 보인다.
- 실제 사용자 매장 데이터처럼 보이는 허구의 수익 숫자를 사용하지 않는다.
- 모바일 360px에서 가로 스크롤과 잘림이 없다.

### S02. 단계형 회원가입·로그인

입력 순서: 계정 → 비밀번호 → 필수 약관 → 완료

API:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/token/refresh`
- `POST /api/v1/auth/logout`

완료 조건:

- 오류는 해당 필드 아래에 표시한다.
- 비밀번호 표시 전환 버튼은 입력창 우측 44px 터치 영역을 확보한다.
- refresh token rotation과 로그아웃 폐기를 검증한다.

### S03. 온보딩 허브

표시 단계: 매장 → 재료 → 구매가격 → 메뉴·레시피 → 판매량 → 첫 분석

API:

- `GET /api/v1/onboarding`
- `PATCH /api/v1/onboarding/current-step`

완료 조건:

- 새로고침과 재로그인 후에도 완료 단계가 유지된다.
- 서버가 단계 완료 조건을 판정한다.
- 사용자가 미완료 단계를 건너뛸 수 없다.

### S04. 재료 등록

입력: 재료명, KAMIS 후보, 구매 단위, 구매 수량, 구매가격, 구매일, 공급처(선택)

즉시 출력:

- 표준단위 환산가격
- KAMIS 연결 상태
- 시장가격 대비 차이

API:

- `GET /api/v1/market/items?query=`
- `POST /api/v1/store-ingredients`
- `POST /api/v1/store-ingredients/{id}/market-mappings`
- `POST /api/v1/purchase-prices`

완료 조건:

- KAMIS 매핑이 불확실하면 강제 연결하지 않는다.
- 변환 불가능한 단위는 사용자 확인 상태로 저장한다.
- 저장 후 “다음 재료”와 “메뉴 만들기” 중 하나를 선택할 수 있다.

### S05. 메뉴·레시피 등록

입력: 메뉴명, 판매가, 판매 채널, 재료별 사용량

즉시 출력: 1개 판매 원가, 원가율, 예상 마진

API:

- `POST /api/v1/menus`
- `POST /api/v1/menus/{id}/recipe-items:replace`
- `POST /api/v1/menus/{id}:clone`
- `GET /api/v1/menus/{id}/cost-preview`

완료 조건:

- 레시피 전체 저장은 하나의 transaction으로 처리한다.
- 같은 재료가 중복 등록되지 않는다.
- 사용량 변경 후 300ms 이내에 로컬 미리보기를 갱신하고 저장 후 서버 계산값으로 교정한다.

### S06. 판매량 빠른 입력

입력: 날짜, 메뉴별 수량, 채널

기능: 전일 값 불러오기, 숫자 스테퍼, 일괄 저장

API:

- `GET /api/v1/sales/daily?date=`
- `PUT /api/v1/sales/daily`
- `POST /api/v1/sales/imports`

완료 조건:

- 날짜·메뉴·채널 조합은 중복 저장되지 않는다.
- 같은 요청을 재전송해도 idempotency key로 중복이 생기지 않는다.
- 잘못된 CSV는 오류 행과 이유를 돌려준다.

### S07. 오늘

우선순위:

1. 데이터가 부족하면 다음 입력 행동
2. 데이터가 충분하면 이번 달 예상 이익
3. 가장 중요한 가격·손익 알림 한 개
4. 빠른 입력 세 개
5. 가격 전망 또는 119 진입

API:

- `GET /api/v1/dashboard/today`

완료 조건:

- 주요 카드는 모바일 첫 화면에서 최대 3개다.
- 알림이 여러 개면 서버에서 우선순위를 결정해 한 개만 반환한다.
- 빈 상태에서도 무엇을 입력해야 하는지 분명하다.

### S08. 시장과 품목 상세

구성: 시장 브리핑 보드, 품목 검색, 실제 가격 그래프, 7일·30일 전망, 80% 예측구간, 기준일, 신뢰등급

시장 브리핑:

- 최신 완료 거래일 기준 도매시장 거래량·반입량 TOP3
- 직전 유효 거래일 대비 오늘 절대 등락률 TOP3
- 오늘 급등 TOP3와 급락 TOP3 상세 보기
- 오늘 가격 대비 내일 중앙 예측값의 예상 변동 TOP3
- 모든 순위에 기준일·단위·출처·수집상태 표시
- 내일 예상 순위에는 80% 예측구간과 신뢰등급 표시

주의:

- 도매시장 거래량을 소비량으로 표현하지 않는다.
- 비교 단위·품종·등급이 다른 가격을 같은 순위로 계산하지 않는다.
- 신뢰등급 기준 미달 또는 운영 미채택 모델의 품목은 예측 순위에서 제외한다.

추가 표시:

- 기본 가격전망
- 기상·수급 반영 후 전망
- 잔차 보정 후 최종 전망
- 이번 예측의 기상 보정량과 잔차 보정량
- 주요 주산지와 사용한 예보 발행시각
- 폭염·호우·한파·태풍 등 위험요인

API:

- `GET /api/v1/market/summary`
- `GET /api/v1/market/items/{id}/prices`
- `GET /api/v1/market/items/{id}/forecast?horizon=30`

완료 조건:

- 시장 요약 API는 거래량·오늘 변동·내일 예상 변동 TOP3와 각 순위의 산출 기준을 반환한다.
- 최신 수집 실패 시 마지막 성공 기준일과 stale 경고를 표시한다.
- 실제 관측값과 예측값을 색과 선 형태로 함께 구분한다.
- 예측구간을 숨기지 않는다.
- 기본 예측과 최종 예측의 차이를 사용자가 펼쳐볼 수 있다.
- “기상 때문에 얼마가 조정되었는지”를 원화와 비율로 표시한다.
- 예보가 없는 12~30일 구간은 평년 기후·1개월 전망 기반 시나리오임을 명확히 표시한다.
- 60일·90일은 데이터가 부족한 동안 비활성화하고 사유를 표시한다.

### S09. 내 가게 영향

질문: “이 재료 가격이 오르면 어떤 메뉴가 가장 위험한가?”

출력:

- 영향 메뉴 순위
- 메뉴별 원가 상승률
- 월 예상 이익 변화 범위
- 계산에 사용한 레시피와 판매기간
- 시나리오 비교 진입

API:

- `GET /api/v1/impact/ingredients/{store_ingredient_id}`
- `POST /api/v1/scenarios/cost-change`

완료 조건:

- 가격 상승률, 사용량, 판매량을 모두 서버 계산식으로 재현할 수 있다.
- 데이터 부족 시 숫자 대신 필요한 데이터와 최소 기간을 안내한다.

### S10. 자영업 119

대화 흐름:

1. 질문 의도 분류
2. 허용된 읽기 도구 호출
3. 문서 RAG 검색
4. 수치 결과 검증
5. 상황·영향·대안·기준을 구조화해 응답
6. 사용자 동의 후 행동계획 저장

API:

- `POST /api/v1/chat/threads`
- `POST /api/v1/chat/threads/{id}/messages`
- `GET /api/v1/chat/threads/{id}/events`
- `POST /api/v1/action-plans/prepare`
- `POST /api/v1/action-plans/{id}/confirm`

완료 조건:

- 답변마다 데이터 기준일, 매장 데이터 기간, 문서 출처, 모델 버전을 펼쳐볼 수 있다.
- 숫자는 tool output과 100% 일치해야 한다.
- 쓰기 작업은 확인 화면과 confirmation token을 거친다.

### S11. 행동계획·회고

필드: 목표, 실행 항목, 시작일, 점검일, 성공 기준, 중단 기준, 상태, 실제 결과

API:

- `GET /api/v1/action-plans`
- `PATCH /api/v1/action-plans/{id}`
- `POST /api/v1/action-plans/{id}/reviews`

완료 조건:

- 계획 생성 당시 근거가 이후에도 보존된다.
- 점검 시 예상값과 실제값을 비교한다.
- 과거 계획은 동일 매장의 향후 RAG 기억으로 사용할 수 있다.

---

## 5. UI/UX 실행 규격

### 디자인 원칙

- 한 화면에서 하나의 중요한 결정을 요구한다.
- 표보다 요약, 요약보다 다음 행동을 먼저 보여준다.
- 카드 전체를 중첩하지 않는다.
- 아이콘은 Lucide 하나만 사용한다.
- 기능이 없는 장식 요소를 추가하지 않는다.
- 모든 화면에 빈 상태·로딩·저장 중·성공·오류·데이터 부족 상태를 설계한다.

### 레이아웃 토큰

| 항목 | 모바일 | 데스크톱 |
|---|---:|---:|
| 좌우 여백 | 16px | 24px |
| 콘텐츠 최대 폭 | 100% | 1160px |
| 섹션 간격 | 32px | 48px |
| 카드 내부 여백 | 16px | 20px |
| 관련 요소 간격 | 8~12px | 8~12px |
| 버튼 높이 | 48px | 44~48px |
| 입력창 높이 | 48px | 44~48px |
| 터치 영역 | 최소 44px | 최소 40px |
| 카드 모서리 | 8px | 8px |

### 타이포와 숫자

- 본문 15~16px, 보조정보 최소 12px
- 모바일 페이지 제목 24px, 핵심 숫자 28~32px
- 금액과 비율에는 `font-variant-numeric: tabular-nums`
- 금액 단위는 본 숫자보다 한 단계 작고 옅게 표시
- 문장형 설명은 카드당 두 줄을 기본 상한으로 사용

### 아이콘과 균형

- 아이콘 canvas 24×24px, glyph 18~20px
- 아이콘과 라벨 간격 8px
- 아이콘 버튼은 44×44px 안에서 optical center 기준 정렬
- 같은 계층은 동일한 stroke width와 색을 사용
- 삭제와 위험 동작에만 Danger 색상 사용
- 아이콘 단독 버튼에는 tooltip과 접근성 라벨을 제공

### 컬러 역할

- Primary: 주요 행동과 선택 상태
- Success: 저장·연결·완료
- Warning: 데이터 부족·신뢰도 보통
- Danger: 삭제·손실 위험·실행 중단
- 실제값과 예측값은 색뿐 아니라 실선·점선으로 구분
- WCAG AA 명암비를 충족한다.

### 모션

- 일반 transition 180ms
- 단계 전환 280ms
- opacity와 8~16px 이동을 기본으로 사용
- 저장 성공은 1회 피드백 후 정적 상태로 전환
- `prefers-reduced-motion`에서 이동 효과를 제거

### UX 검수 체크

- 360×800, 390×844, 768×1024, 1440×900 화면 검수
- 200% 확대에서 텍스트와 버튼이 잘리지 않음
- 키보드만으로 주요 흐름 완료
- 오류 발생 후 입력값 유지
- 뒤로 가기 후 단계와 스크롤 위치가 예측 가능
- 실사용자 5명 중 4명 이상이 도움 없이 첫 분석 완료

---

## 6. 시스템 아키텍처

```text
Vue 3 Web
  -> Django REST API
      -> PostgreSQL: 매장·메뉴·가격·판매·계획
      -> Redis/Celery: 가격·기상·거래량 수집, 예측, 문서 처리
      -> Object Storage: 원본 응답·문서·모델
      -> FastAPI ML Service
          -> Base Price Model
          -> Weather & Supply Impact Model
          -> Residual Correction Model
          -> Interval Calibration
      -> LLM Orchestrator
          -> 제한된 분석 도구 API
          -> pgvector 문서 검색
```

### 저장 역할

| 데이터 | 저장소 | 조회 방식 |
|---|---|---|
| 매장·재료·메뉴·판매 | PostgreSQL | store scope SQL |
| KAMIS 일별 가격 | PostgreSQL | 품목·지역·단위 시계열 SQL |
| 도매시장 경락가격·거래량 | PostgreSQL | 품목·산지·시장별 수급 시계열 |
| ASOS·농업기상 관측 | PostgreSQL/Parquet | 주산지·일자별 집계 |
| 단기·중기·1개월 기상전망 | PostgreSQL | 발행시각별 forecast snapshot |
| 생산량·재배면적·농업관측 | PostgreSQL/Document | 연·월별 구조 변수와 RAG |
| 예측 결과 | PostgreSQL | 모델 버전별 조회 |
| 문서·시장 요약·과거 전략 | PostgreSQL + pgvector | metadata filter + vector |
| 원본 API·보고서·모델 | S3/MinIO | object key |
| 작업 상태·캐시 | Redis | TTL·queue |

### 멀티테넌트 원칙

- 모든 매장 소유 테이블에 `store_id`를 둔다.
- ORM 조회는 `StoreScopedQuerySet` 또는 동등한 공통 진입점을 사용한다.
- API permission과 서비스 계층에서 이중 검증한다.
- 테스트에서 두 매장을 항상 생성해 교차 접근을 검증한다.
- RAG metadata에도 `store_id`와 공유 범위를 명시한다.

---

## 7. 최소 데이터 모델

### P0 운영 테이블

| 테이블 | 핵심 필드 | 주요 제약 |
|---|---|---|
| Store | id, name, business_type, region | owner 존재 |
| StoreMember | store_id, user_id, role | store+user unique |
| OnboardingProgress | store_id, current_step, completed_steps | store unique |
| MarketItem | code, name, variety, grade, standard_unit | source code unique |
| MarketPriceObservation | item_id, date, region, market_type, unit, price | 자연키 unique |
| IngestionRun | source, started_at, status, counts, error | 재실행 추적 |
| CropProductionRegion | item_id, region_code, weight, valid_from | 품목별 주산지 비중 |
| CropGrowthStage | item_id, region_id, stage, start_day, end_day | 생육단계 유효기간 |
| WeatherStationMapping | region_id, station_id, distance, weight | 다중 관측소 가중치 |
| WeatherObservation | station_id, observed_at, variables, quality | 관측 원본과 품질 |
| WeatherForecastSnapshot | issued_at, valid_at, grid, variables, provider | 발행시각 보존 |
| WeatherExposureFeature | item_id, region_id, as_of, windows, anomalies | 누적·이상 기상 |
| WholesaleAuctionObservation | date, market, item, origin, volume, price | 가격·거래량 자연키 |
| ProductionStatistic | item_id, region, period, area, yield, production | 기준시점과 출처 |
| StoreIngredient | store_id, name, base_unit, active | store scope |
| IngredientMarketMapping | ingredient_id, market_item_id, confidence, status | 확인 상태 |
| PurchasePriceObservation | ingredient_id, purchased_at, quantity, unit, total_price | Decimal, 양수 |
| Menu | store_id, name, selling_price, active | store+name 조건 |
| RecipeItem | menu_id, ingredient_id, quantity, unit | menu+ingredient unique |
| DailyMenuSale | store_id, menu_id, date, channel, quantity | 조합 unique |
| ForecastRun | target, as_of, model_version, status | 상태 추적 |
| ForecastPoint | run_id, horizon, median, intervals | 구간 순서 검증 |
| ForecastComponent | run_id, horizon, base, weather_delta, residual_delta | 단계별 보정량 |
| OutOfFoldForecast | fold_id, target_date, horizon, prediction, actual | 잔차 학습 전용 |
| ResidualObservation | oof_id, residual, residual_type | OOF에서만 생성 |
| ForecastCalibration | model_version, horizon, coverage, correction | 구간 보정 |
| KnowledgeDocument | source, published_at, metadata, object_key | source 추적 |
| KnowledgeChunk | document_id, content, embedding, metadata | pgvector |
| ChatThread | store_id, title, created_by | store scope |
| ToolExecutionLog | thread_id, tool, input, output, status | 감사 로그 |
| ActionPlan | store_id, thread_id, goal, dates, criteria, status | 근거 snapshot |
| ActionPlanReview | plan_id, actual_result, metrics, reviewed_at | 이력 보존 |

### 표준 단위

- 질량: `g`
- 부피: `ml`
- 개수: `ea`
- 통화: `KRW`
- 비율: API에서는 0~1 decimal로 저장하고 UI에서 %로 표시

단위 변환이 확인되지 않은 데이터는 계산에서 제외하고 `UNIT_MAPPING_REQUIRED` 상태를 반환한다.

---

## 8. 팀별 개발 백로그

### 팀 1. 프론트엔드·UI/UX

P0:

1. 디자인 토큰과 반응형 shell
2. 공통 Button, Input, Select, Stepper, Modal, Toast, Skeleton
3. 단계형 회원가입
4. 온보딩 허브
5. 재료 등록 마법사
6. 메뉴·레시피 등록 마법사
7. 판매량 빠른 입력
8. 오늘 화면
9. 시장 품목 상세와 예측구간 그래프
10. 내 가게 영향 화면
11. 119 채팅과 근거 패널
12. 행동계획 확인·저장·회고
13. 핵심 E2E Playwright 테스트

필수 산출물:

- Figma flow와 화면 상태표
- Storybook 컴포넌트
- API client 자동 생성 또는 타입 동기화
- 모바일·데스크톱 스크린샷 검수 기록

### 팀 2. 백엔드·API

P0:

1. JWT 인증과 token rotation
2. Store, StoreMember, store scope
3. 온보딩 상태 머신
4. 재료·매핑·구매가격 API
5. 메뉴·레시피 transaction API
6. 판매량 일괄 입력과 idempotency
7. 원가·마진 계산 서비스
8. 가격·판매 변화 시나리오 서비스
9. KAMIS 조회 API
10. 예측 gateway와 fallback
11. LLM 허용 도구 API
12. 행동계획 prepare/confirm API
13. OpenAPI·권한·계약 테스트

필수 산출물:

- `/api/v1` OpenAPI
- 오류 코드 사전
- 권한 매트릭스
- 계산식 단위 테스트
- 두 매장 교차 접근 보안 테스트

### 팀 3. DB·데이터 엔지니어링

P0:

1. ERD와 migration
2. KAMIS 일별 가격 raw 수집과 증분 upsert
3. 전국 도매시장 경락가격·거래량 수집
4. 기상청 ASOS와 농촌진흥청 농업기상 수집
5. 기상청 단기·중기·1개월 전망을 발행시각별 snapshot으로 저장
6. 품목별 주산지·작부체계·생육단계 매핑
7. 가격·거래량·주산지·기상 시공간 정렬
8. 품목·지역·등급·단위 정규화
9. 재수집·중복 방지·실패 재처리
10. 데이터 품질 규칙과 이슈 테이블
11. 대표 품목 5개 데이터 프로파일링
12. point-in-time 학습 snapshot과 OOF 예측 저장소 생성
13. 시장 주간 요약 문서 생성
14. 문서 metadata와 pgvector 적재
15. 백업·복구와 lineage 문서

필수 산출물:

- 데이터 사전
- source-to-target mapping
- ingestion dashboard
- 품목별 가격·거래량·기상 누락률과 가용기간 보고서
- 품목별 주산지 및 기상 관측소 매핑표
- 예보 발행시각과 유효시각이 보존된 weather forecast archive
- 동일 조건으로 재생성 가능한 feature dataset

### 팀 4. ML·RAG·LLM

P0:

1. 마지막 값·계절 나이브 baseline
2. 가격·거래량 기반 Base Price Model
3. 주산지 기상 노출과 수급 충격 feature 연구
4. Weather & Supply Impact Model
5. rolling-origin OOF 예측과 잔차 label 생성
6. horizon별 Residual Correction Model
7. `base → weather → residual` 단계별 ablation
8. 7일·30일 rolling-origin backtest
9. 중앙값·80% 구간·신뢰등급·conformal calibration
10. 단계별 보정량을 반환하는 예측 API와 ModelRegistry
11. 시장 요약·운영 문서 hybrid retrieval
12. 허용 도구 기반 LLM orchestration
13. 숫자 일치 post-validation
14. 자영업 119 구조화 응답
15. 행동계획 초안 생성
16. 예측·RAG·LLM 평가셋과 결과 보고서

필수 산출물:

- 모델 카드
- 품목별 `baseline / base / base+weather / base+weather+residual` backtest 표
- 기상 feature 중요도와 주산지·생육단계별 영향 분석
- 잔차 자기상관·편향·분포 진단
- RAG 검색 평가
- tool selection·숫자 일치·근거 포함 평가
- 답변 불가능 상황의 안전 응답

---

## 9. 팀 간 계약

### 프론트엔드와 백엔드

- OpenAPI를 단일 계약으로 사용한다.
- 모든 화면은 `loading`, `empty`, `success`, `validation_error`, `server_error`, `insufficient_data` 응답을 정의한다.
- 오류 형식은 `code`, `message`, `fields`, `request_id`로 고정한다.
- 금액은 문자열 Decimal 또는 명시된 integer KRW로 전달한다.

### 백엔드와 DB

- migration은 DB팀 리뷰 후 병합한다.
- unique constraint와 이력 보존 정책을 문서화한다.
- 삭제는 도메인별 hard/soft delete를 미리 결정한다.
- 원가 계산에 사용된 가격 관측 ID를 추적할 수 있어야 한다.

### DB와 ML

- 모든 학습 행은 `as_of` 기준 point-in-time correctness를 지킨다.
- feature 정의, 단위, 결측 처리, source를 데이터 사전에 기록한다.
- 학습·검증·테스트 snapshot ID를 ModelRegistry에 연결한다.

### 백엔드와 ML

예측 최소 응답:

```json
{
  "target_type": "market_price",
  "target_id": "ITEM_ONION",
  "as_of": "2026-06-24",
  "horizon_days": 30,
  "base_prediction": "1740.00",
  "weather_adjustment": "85.00",
  "residual_adjustment": "25.00",
  "median": "1850.00",
  "lower_80": "1650.00",
  "upper_80": "2050.00",
  "confidence": "MEDIUM",
  "weather_forecast_issued_at": "2026-06-24T06:00:00+09:00",
  "model_version": {
    "base": "base-price-v1",
    "weather": "weather-impact-v1",
    "residual": "residual-correction-v1",
    "calibration": "interval-calibration-v1"
  },
  "data_quality": []
}
```

### LLM과 서비스 도구

- 읽기 도구와 쓰기 도구를 분리한다.
- 도구 입력·출력은 JSON schema로 검증한다.
- 쓰기 도구는 prepare와 confirm 두 단계로 호출한다.
- 모든 도구 실행은 request ID, store ID, latency, 결과 상태를 기록한다.
- timeout 시 답변을 꾸며내지 않고 사용 가능한 결과만 설명한다.

---

## 10. 예측·RAG·LLM 구현 기준

### 가격 예측

MVP 대상: 데이터 품질과 사용자 영향도가 높은 대표 품목 최대 5개

예측 기간:

- P0: 1일, 7일, 30일
- P1: 60일
- 보류: 90일

#### Stage 0. 비교 기준

- 마지막 값
- 계절 나이브
- 이동평균 또는 ETS

복잡한 모델이 이 기준보다 좋아지지 않으면 운영에 채택하지 않는다.

#### Stage 1. Base Price Model

목표: 가격과 시장 수급 자체가 가진 추세·계절성·자기상관을 먼저 예측한다.

입력:

- KAMIS 가격 lag 1·2·7·14·28·365
- rolling mean·median·std·min·max
- 전년 동기와 평년 대비 편차
- 도매시장 경락가격·거래량·반입량
- 품목·품종·등급·시장·지역
- 요일·공휴일·명절·월·계절
- 재배면적·생산량·저장량 등 기준시점에 공개된 구조 변수

후보:

- SARIMAX
- LightGBM Quantile global model
- 두 모델의 validation 기반 앙상블

출력:

```text
base_prediction(t, h)
```

#### Stage 2. Weather & Supply Impact Model

목표: 과거 가격만으로 아직 반영하지 못한 기상 충격이 생산·출하·거래량과 가격에 미치는 추가 변동을 학습한다.

핵심은 시장 소재지 날씨가 아니라 품목별 주산지 날씨를 사용하는 것이다. 품목마다 주산지 비중을 두고, 생육단계별로 기상 노출을 집계한다.

기상 feature:

- 평균·최저·최고기온과 평년 편차
- 누적강수량, 강수일수, 최대 일강수
- 일조·일사량
- 상대습도, 풍속
- 토양온도와 토양수분
- 폭염일수, 한파일수, 열대야
- 호우·태풍·강풍·대설 특보
- growing degree days
- 연속 무강수일수와 과습일수
- 3·7·14·30·60·90일 누적·지연 노출

수급 매개 feature:

- 도매시장 거래량과 반입량 변화
- 산지·시장별 거래량 비중
- 재배면적·단수·생산량
- 농업관측센터 출하·생산 전망
- 병해충 발생정보

권장 학습 방식:

1. 기상 노출로 거래량 또는 출하량 이상치를 먼저 예측한다.
2. 예측된 수급 충격이 가격에 주는 보정량을 학습한다.
3. 직접 가격 보정 모델과 비교하고 validation 성능이 좋은 방식을 채택한다.

출력:

```text
weather_adjustment(t, h)
stage2_prediction(t, h)
  = base_prediction(t, h) + weather_adjustment(t, h)
```

#### Stage 3. Residual Correction Model

목표: 1·2단계가 반복적으로 과대·과소 예측하는 패턴을 학습해 최종 편향을 줄인다.

잔차 label:

```text
residual(t, h)
  = log(actual_price(t+h))
  - log(stage2_prediction(t, h))
```

중요 규칙:

- 잔차 학습용 예측은 학습 데이터에 다시 맞춘 in-sample prediction이 아니라 rolling-origin OOF prediction으로 생성한다.
- 각 horizon 1·7·30일의 잔차 모델을 분리하거나 horizon을 명시적 feature로 사용한다.
- test fold의 실제 가격은 평가 전까지 어떤 feature와 보정에도 사용하지 않는다.
- 직전까지 공개된 잔차 lag, 모델 간 disagreement, 예측구간 폭, 데이터 품질, 최근 체제 변화만 사용한다.
- 테스트 기간을 본 뒤 보정량을 수동 조정하지 않는다.

잔차 feature:

- 최근 OOF residual lag와 rolling bias
- 품목·시장·계절별 평균 잔차
- base model과 weather model의 disagreement
- 최근 변동성·가격 급등락 regime
- 예보와 관측의 최근 기상 bias
- 거래량 예측 오차
- 결측률·대체값 비율·매핑 confidence

후보:

- Ridge/ElasticNet residual model
- LightGBM residual regressor
- 데이터가 충분해진 뒤 TCN·LSTM residual model

최종 예측:

```text
final_log_price(t, h)
  = log(stage2_prediction(t, h))
  + predicted_residual(t, h)

final_price(t, h)
  = exp(final_log_price(t, h))
```

품목별 현실적 상·하한과 전일 대비 변화율 guardrail을 적용하되, clipping 발생 여부를 로그에 남긴다.

#### 미래 기상 사용 규칙

- 1~3일: 기상청 단기예보의 발행시각 snapshot 사용
- 4~11일: 기상청 중기예보 사용
- 12~30일: 기상청 1개월 전망, 평년 기후, 복수 기상 시나리오 사용
- 과거 학습: ASOS·농업기상 관측으로 기상 민감도를 학습
- 운영 재현 평가: 가능하면 과거에 실제 발행된 예보 archive를 사용

실제 관측 기상을 미래 예보인 것처럼 test feature에 넣은 결과는 `oracle experiment`로만 기록하고 운영 성능으로 보고하지 않는다. 과거 예보 archive가 부족하면 관측 기상에 과거 예보 오차 분포를 주입한 시나리오로 강건성을 추가 평가한다.

#### 예측구간 보정

Quantile 모델의 80% 구간을 그대로 신뢰하지 않고 validation residual로 horizon·품목별 conformal calibration을 적용한다. 극단 기상 또는 데이터 부족 시 구간을 넓히고 신뢰등급을 낮춘다.

평가:

- WAPE, MASE, Pinball loss
- 80% interval coverage와 interval width
- bias
- rolling-origin evaluation
- 기상 충격 구간과 평시 구간 분리 평가
- 1·7·30일 horizon별 평가
- 단계별 ablation: baseline / base / base+weather / base+weather+residual
- 잔차 자기상관과 평균 편향
- Diebold-Mariano test 또는 paired bootstrap 95% CI

운영 채택 조건:

- 최종 모델이 baseline과 Base Price Model을 모두 개선
- weather stage가 기상 충격 구간에서 추가 개선
- residual stage가 별도 test fold에서 편향 또는 오차를 추가 개선
- 예측구간 coverage 목표 충족
- 주요 품목에서 치명적인 성능 저하가 없음
- 데이터와 모델 버전을 재현 가능
- 개선이 없는 품목·horizon은 해당 보정단계를 자동으로 0 처리

### 검증된 외부 데이터 구성

#### 가격·거래량

| 출처 | 확보 데이터 | 활용 |
|---|---|---|
| aT KAMIS 농축수산물 일자별 도소매 가격 | 1996년 이후 일별 가격, 품목·품종·등급·지역 | 최종 target, 장기 가격 lag |
| KAMIS Open API | 최신 농수축산물 가격 | 운영 추론과 화면 |
| 농림축산식품부 도매시장 실시간 경락 정보 | 경락일자, 시장, 품목·품종·등급, 낙찰가격, 거래량 | 수급 선행변수 |
| aT 전국 공영도매시장 실시간 경매정보 | 전국 32개 공영도매시장 가격·거래량 | 시장별 수급 검증 |
| 농넷 | 가락·전국도매시장·산지공판장 가격과 거래물량 | 보조 검증과 시장 비교 |

#### 기상·생산

| 출처 | 확보 데이터 | 활용 |
|---|---|---|
| 기상청 ASOS 일·시간자료 | 기온, 강수, 습도, 풍속, 일조, 일사 | 장기 기상 관측 |
| 농촌진흥청 농업기상 상세 관측 | 기온, 습도, 강수, 풍향·풍속, 일사, 토양온도·수분 | 주산지 정밀 노출 |
| 농촌진흥청 주산지 농업기상분석 | 주산지별 일·순·월 기상 | 품목·산지 집계 |
| 기상청 단기예보 | 5km 격자, 글피까지 시간별 예보 | 1~3일 운영 feature |
| 기상청 중기예보 | 11일까지 기온·강수확률·날씨 | 4~11일 운영 feature |
| 기상청 1개월 전망 | 4주 주별 기온·강수 전망 | 12~30일 시나리오 |
| Copernicus ERA5-Land | 1950년 이후 토양수분·강수·기온·복사 등 재분석 | 관측 공백 보완·연구 |
| 통계청 농작물생산조사 | 재배면적, 단수, 생산량 | 구조적 공급 변수 |
| KREI 농업관측센터 | 생산·출하·가격 전망 보고서 | 정형 feature와 RAG |
| 농촌진흥청 병해충발생정보 | 지역·작물별 발생정보 | 생산 충격 보조 변수 |

#### 외부 공개 데이터 사용 판단

Hugging Face에서 확인되는 농산물 가격 데이터 중 일부는 나이지리아 합성 데이터이거나 해외 시장 데이터다. 한국의 품목·유통·기상 구조와 다르므로 BOSSPROFIT 운영 모델의 학습 데이터로 합치지 않는다. 파이프라인 재현과 모델 코드 검증에는 사용할 수 있지만, 국내 성능 수치에는 포함하지 않는다.

### 선행 연구에서 반영할 원칙

- 농산물 가격 예측에서 날씨·지역·거래량 등 다변량 입력을 결합한 연구를 참고한다.
- 선형·계절 성분을 먼저 예측하고 비선형 잔차를 별도 모델로 보정하는 residual learning 구조를 채택한다.
- 잔차 보정이 항상 좋아진다고 전제하지 않고 별도 test fold와 ablation으로 검증한다.
- 작은 농산물 데이터에서는 복잡한 Transformer가 단순 계절 나이브보다 나쁠 수 있으므로 모델 복잡도보다 검증 결과를 우선한다.
- 기온·강수 변동이 단기 식품가격에 미치는 영향은 공간적으로 세분된 가격과 주산지 기상을 함께 사용해 분석한다.

### RAG

SQL로 처리:

- KAMIS 실제 가격
- 내 구매가격
- 메뉴 원가와 판매량
- 예측 결과
- 행동계획 상태

RAG로 처리:

- 정부·시장 수급 보고서
- 가격 변동 원인
- 국제 사건과 원자재 영향 문서
- 외식업 운영 가이드
- 과거 상담 요약
- 동일 매장의 과거 전략과 결과

검색 파이프라인:

1. 질문에서 품목·지역·기간·사건 추출
2. metadata filter
3. dense와 keyword 검색
4. reranking
5. 중복 제거와 최신성 검증
6. 출처가 포함된 context 생성

### 자영업 119 응답 형식

1. 지금 상황
2. 내 매장 영향
3. 예상 손실 또는 변화 범위
4. 오늘 할 일
5. 1주 안에 할 일
6. 선택 가능한 대안
7. 성공 기준
8. 중단 기준
9. 근거와 신뢰도

LLM 금지사항:

- 도구에 없는 숫자 생성
- 직접 SQL 실행
- 다른 매장 데이터 사용
- 출처 없는 사건 단정
- 예측 범위를 확정값으로 표현
- 사용자 확인 없는 저장·수정·삭제

---

## 11. 6주 개발 일정

### Week 1. 계약 고정과 기반

공통:

- E2E 흐름과 P0 범위 동결
- 화면 ID, API path, 테이블 명명 확정
- repo 구조와 CI 기준 확정

팀별:

- Front: 디자인 토큰, app shell, 온보딩 wireframe
- Back: 인증, Store scope, OpenAPI 골격
- Data: ERD, KAMIS·도매거래량·ASOS·농업기상 샘플 수집, 대표 품목 프로파일링
- AI: baseline notebook, rolling-origin 평가 분할, 주산지·생육단계 feature 설계, RAG 문서 schema

주간 데모: 가입 → 빈 온보딩 허브, KAMIS 샘플 데이터 조회

### Week 2. 입력 흐름 완성

- Front: 재료·메뉴·판매 입력
- Back: 재료·레시피·판매 API와 계산 서비스
- Data: 정규화·단위 변환·주산지-관측소 매핑·증분 upsert
- AI: Base Price Model backtest와 데이터 품질 피드백

주간 데모: 신규 사용자가 자신의 첫 메뉴 원가를 계산

### Week 3. 시장 연결

- Front: 시장 검색·품목 상세·내 구매가격 비교
- Back: 시장 조회·영향 계산 API
- Data: 가격·거래량·관측기상·기상예보 snapshot 수집과 품질 모니터링
- AI: Weather & Supply Impact Model, 기상 충격 feature ablation

주간 데모: 양파 시장가격과 내 구매가격 차이를 표시

### Week 4. 예측과 메뉴 영향

- Front: 예측구간 그래프·내 가게 영향·데이터 부족 상태
- Back: ForecastGateway·ScenarioService
- Data: point-in-time feature snapshot·OOF prediction store·ModelRegistry 연계
- AI: 잔차 label 생성, Residual Correction Model, conformal calibration, FastAPI serving

주간 데모: 기본 전망·기상 보정·잔차 보정과 30일 최종 전망이 메뉴 원가에 미치는 영향 표시

### Week 5. 자영업 119

- Front: 채팅·근거 패널·대안 비교·행동계획 확인
- Back: chat orchestration·도구 API·prepare/confirm
- Data: 문서 적재·pgvector·과거 계획 schema
- AI: hybrid retrieval·tool calling·숫자 post-validation

주간 데모: 시장 충격 질문 → 내 매장 영향 → 행동계획 저장

### Week 6. 통합·검증·출시

- E2E 회귀 테스트
- 두 매장 격리 보안 테스트
- 모바일 실사용자 5명 테스트
- 예측·RAG·LLM 평가
- 기상 충격 구간·평시 구간 및 단계별 ablation 검증
- 미래 실제 기상·가격 누수 검사
- 성능·접근성·장애 fallback 검증
- 데모 데이터와 운영 runbook 작성

출시 게이트:

- Critical·High 결함 0건
- 핵심 E2E 100% 통과
- 교차 매장 노출 0건
- LLM 숫자 일치 99% 이상
- KAMIS 최근 7일 수집 성공
- 기상 관측·예보 snapshot과 거래량 최근 7일 수집 성공
- 잔차 보정이 test fold 성능을 악화시키는 품목에서는 자동 비활성화

---

## 12. 개발 티켓 작성 규칙

모든 티켓에는 아래 항목이 있어야 한다.

- 사용자 가치
- 화면 또는 API ID
- 입력과 출력
- 오류·빈 상태
- 의존 티켓
- 보안 조건
- 테스트 방법
- 완료 조건

예시:

**제목:** `[BE][S04] 구매가격 등록과 표준단위 환산`

**완료 조건:**

1. 로그인 사용자의 현재 store에만 저장된다.
2. quantity와 total_price는 0보다 커야 한다.
3. 변환 가능한 단위는 g/ml/ea 기준 가격을 반환한다.
4. 변환 불가능하면 422와 `UNIT_MAPPING_REQUIRED`를 반환한다.
5. 같은 idempotency key 재전송 시 중복 저장되지 않는다.
6. 서비스 단위 테스트와 API contract test가 통과한다.

---

## 13. Definition of Done

### 기능

- 인수 조건과 오류 상태가 구현됨
- OpenAPI 또는 데이터 사전이 갱신됨
- 로그와 request ID로 실패를 추적할 수 있음
- 데이터 기준일과 단위가 화면에 표시됨

### 테스트

- 핵심 계산과 권한 단위 테스트
- API contract test
- 주요 UI 상태 Storybook
- 핵심 흐름 Playwright
- 360px와 1440px 시각 검수

### 보안

- store scope 적용
- 민감정보 로그 제외
- 쓰기 동작 확인 절차
- 다른 매장 데이터 접근 테스트

### AI

- baseline 비교
- base / weather / residual 단계별 ablation
- 모델·데이터 버전
- OOF 잔차 생성과 test leakage 검사
- 기상예보 발행시각 snapshot 추적
- 불확실성과 데이터 부족 표현
- 검색 출처 추적
- tool output과 최종 숫자 일치 검사

---

## 14. 성과지표

### 활성화

- 가입 완료율
- 첫 재료·첫 메뉴 등록률
- 첫 분석 도달률
- 가입 후 첫 분석까지 걸린 시간

### 사용성

- 재료 등록 중앙값 60초 이하
- 첫 메뉴 등록 중앙값 3분 이하
- 사용자 테스트 핵심 과업 성공률 80% 이상
- 모바일 폼 이탈률

### 데이터

- KAMIS 일별 수집 성공률
- 도매시장 거래량·경락가격 수집 성공률
- 농업기상 관측과 기상예보 snapshot 수집 성공률
- 주산지·관측소 매핑 커버리지
- 내 재료와 시장 품목 매핑률
- 단위 미확인 비율
- 판매량 입력 일수

### AI

- baseline 대비 WAPE·MASE 개선
- Base Price Model 대비 기상 보정 후 성능 개선
- 기상 보정 대비 잔차 보정 후 test 성능 개선
- 평시·폭염·호우·한파·태풍 구간별 오차
- horizon별 잔차 평균, 자기상관, RMSE
- 80% 예측구간 coverage
- RAG Recall@k와 근거 적합도
- tool 선택 정확도
- 숫자 일치율
- 행동계획 저장률과 실행 완료율

---

## 15. 주요 리스크와 즉시 대응

| 리스크 | 조기 신호 | 대응 |
|---|---|---|
| KAMIS 품목과 실제 구매품 불일치 | 매핑 보류 증가 | 다대다 후보, 사용자 확인, confidence 저장 |
| 품목별 이력 부족 | 예측구간 과도 | 대표 품목 제한, baseline, 7·30일 우선 |
| 실제 미래 기상 사용으로 인한 누수 | 비현실적으로 높은 test 성능 | 예보 발행시각 snapshot, oracle 실험 분리 |
| 주산지와 시장 날씨 혼동 | 기상 feature 중요도 불안정 | 품목별 주산지 비중과 생육단계 매핑 |
| 잔차 모델 과적합 | validation만 개선, test 악화 | rolling OOF residual, 단순 모델 우선, 자동 비활성화 |
| 30일 일별 날씨 예보 부재 | 장기 전망 과신 | 1개월 전망·평년·복수 시나리오와 넓은 구간 |
| 가격과 거래량 동시 내생성 | 설명 왜곡 | 시차 feature, 공개시점 관리, ablation |
| 단위 오류 | 원가 급등락 | 표준단위와 변환 근거 저장, 미확인 계산 제외 |
| LLM 숫자 환각 | tool output 불일치 | structured output와 post-validation |
| UI 과밀 | 온보딩 이탈 | 단계 공개, 카드 3개, CTA 1개 |
| 팀 간 계약 변경 | 반복 재작업 | OpenAPI·ERD 주 2회 계약 리뷰 |
| 범위 폭발 | P0 지연 | 세무·재고·POS·자동발주 제외 유지 |
| 외부 API 장애 | 최신 가격 누락 | 마지막 성공 기준일 표시, 재시도, stale 경고 |

---

## 16. 최종 인수 시나리오

QA는 아래 시나리오를 실제 모바일 화면에서 처음부터 끝까지 수행한다.

1. 사용자 A가 가입하고 “성민우동” 매장을 만든다.
2. 양파를 등록하고 KAMIS 양파 품목과 연결한다.
3. 20kg 42,000원 구매 기록을 저장한다.
4. 어묵우동 메뉴와 양파 80g을 포함한 레시피를 등록한다.
5. 최근 7일 판매량을 입력한다.
6. 현재 1개 판매 원가와 원가율을 확인한다.
7. 양파의 실제 가격과 30일 전망·80% 구간을 확인한다.
8. 기본 예측, 기상 보정량, 잔차 보정량과 사용한 기상예보 발행시각을 확인한다.
9. 양파 가격 10% 상승 시 어묵우동 원가와 월 이익 변화를 확인한다.
10. 119에 “양파값이 더 오르면 가격 인상 말고 무엇을 할 수 있어?”라고 묻는다.
11. AI가 근거, 대안, 성공·중단 기준을 제시한다.
12. 사용자가 한 대안을 선택해 2주 행동계획으로 저장한다.
13. 사용자 B로 로그인했을 때 사용자 A의 어떤 데이터도 조회되지 않는다.
14. test 기간의 실제 가격과 실제 미래 기상이 예측 feature에 포함되지 않았음을 로그로 검증한다.

이 시나리오가 통과하면 BOSSPROFIT은 단순한 ERP 화면이나 RAG 데모가 아니라, 시장 데이터가 매장 의사결정과 실제 행동으로 연결되는 첫 제품 단위를 완성한 것이다.

---

## 17. 구현 조사 출처

### 국내 운영 데이터

- [aT KAMIS 농축수산물 일자별 도소매 가격](https://www.data.go.kr/data/15072357/fileData.do)
- [KAMIS 가격정보 Open API](https://www.kamis.or.kr/customer/reference/openapi_list.do)
- [기상청 ASOS 일자료 조회서비스](https://www.data.go.kr/data/15059093/openapi.do)
- [농촌진흥청 농업기상 상세 관측데이터](https://www.data.go.kr/data/15078194/openapi.do)
- [농촌진흥청 주산지 농업기상분석정보](https://www.data.go.kr/data/15108406/openapi.do)
- [기상청 단기예보 조회서비스](https://www.data.go.kr/data/15084084/openapi.do)
- [기상청 중기예보 조회서비스](https://www.data.go.kr/data/15059468/openapi.do)
- [기상청 1개월 전망](https://www.weather.go.kr/w/climate/prediction/month1.do)
- [농림축산식품부 도매시장 실시간 경락 정보](https://www.data.go.kr/data/15140549/openapi.do)
- [aT 전국 공영도매시장 실시간 경매정보](https://www.data.go.kr/data/15141808/openapi.do)
- [통계청 농작물생산조사](https://kostat.go.kr/statDesc.es?act=view&mid=a10501010000&sttr_cd=S005011)
- [KREI 농업관측센터](https://aglook.krei.re.kr/)
- [Copernicus ERA5-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land)

### 모델 설계 참고 연구

- Li, B. et al. (2025), *A Forecasting Approach for Wholesale Market Agricultural Product Prices Based on Hybrid Residual Correction*
- Gu, Y. H. et al. (2022), *Forecasting Agricultural Commodity Prices Using Dual Input Attention LSTM*
- Goel, H. et al. (2017), *R2N2: Residual Recurrent Neural Networks for Multivariate Time Series Forecasting*
- Bhardwaj, M. R. et al. (2023), *An Innovative Deep Learning Based Approach for Accurate Agricultural Crop Price Prediction*
- Adam, C. et al. (2025), *The Impact of Temperature and Rainfall Volatility on Food Prices*
- Muhammad, T. et al. (2026), *A Benchmark of Classical and Deep Learning Models for Agricultural Commodity Price Forecasting*

이 출처들은 데이터 사용 가능성과 모델 구조의 근거다. 특정 연구의 성능 수치를 BOSSPROFIT의 예상 성능으로 간주하지 않으며, 국내 데이터의 별도 rolling backtest 결과만 제품 성능으로 보고한다.
