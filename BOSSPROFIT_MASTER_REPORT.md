# BOSSPROFIT 통합 제품·기술 기획 보고서

> 소상공인을 위한 식재료 가격 예측, 매장 손익 관리, 위기 대응 AI 미니 ERP

문서 상태: 개발 기준 초안  
대상 조직: 프론트엔드팀, 백엔드팀, DB·데이터팀, ML·RAG팀  
핵심 사용자: 음식점을 운영하지만 데이터·회계·IT 도구에 익숙하지 않은 자영업자

---

## 1. 보고서 목적

이 문서는 BOSSPROFIT을 아이디어 또는 시연용 대시보드가 아니라 실제 서비스로 발전시키기 위한 통합 실행 기준이다.

특히 다음 질문에 명확하게 답하는 것을 목표로 한다.

1. 어떤 자영업자의 문제를 해결하는가?
2. 사용자가 어떤 순서로 서비스를 이용하는가?
3. 네 개 팀은 각각 무엇을 만들고 어디까지 책임지는가?
4. 팀 사이에서 어떤 데이터와 API 계약을 사용해야 하는가?
5. 예측 모델과 RAG·LLM은 어떤 역할을 맡는가?
6. UI/UX를 어떤 수치와 원칙으로 검수할 것인가?
7. MVP에서 반드시 만들 것과 만들지 않을 것은 무엇인가?

---

## 2. 서비스 문제의식

### 2.1 반복적으로 변하는 식재료 가격

자영업자는 매달 또는 매주 달라지는 식재료 가격에 직접 노출된다.

가격 변동의 주요 원인은 다음과 같다.

- 기온, 강수량, 폭염, 한파, 태풍
- 작황, 출하량, 저장량, 병충해
- 명절과 계절별 수요
- 유가와 물류비
- 환율과 수입 원자재 가격
- 수출입 제한과 검역 정책

식재료 가격은 자주 변하지만 음식점은 메뉴 가격을 그때마다 바꾸기 어렵다. 가격을 지나치게 자주 변경하면 고객 저항과 브랜드 신뢰 하락이 발생할 수 있기 때문이다.

현재 대부분의 소규모 매장은 납품업체가 가격을 올린 후에야 변화를 인지한다. BOSSPROFIT은 이를 다음과 같이 바꾼다.

```text
사후 인지
→ 가격 상승 후 손실 확인

사전 대비
→ 가격 상승 가능성 확인
→ 내 메뉴 영향 계산
→ 구매·레시피·판매 전략 준비
```

### 2.2 예측하기 어려운 외부 충격

국제 분쟁, 유가 급등, 수출 제한, 감염병, 항만 폐쇄처럼 갑작스러운 사건은 과거 가격 패턴만으로 정확하게 예측하기 어렵다.

이때 자영업자의 문제는 사건 자체를 예측하지 못했다는 것이 아니다.

실제 문제는 다음과 같다.

- 사건이 내 매장에 어떤 영향을 줄지 알기 어렵다.
- 어떤 비용부터 오를지 알기 어렵다.
- 가격 인상, 메뉴 조정, 구매량 변경 중 무엇을 선택할지 어렵다.
- 언제 전략을 중단하거나 수정해야 할지 기준이 없다.
- 검색한 정보는 많지만 내 매장 데이터와 연결되지 않는다.

BOSSPROFIT은 이를 해결하는 `자영업 119`를 제공한다.

```text
시장 사건
→ 관련 원자재·물류 영향 검색
→ 내 재료·메뉴·판매 데이터 조회
→ 가격·판매 시나리오 계산
→ 단기·중기 행동계획 제안
→ 실행 결과 기록과 재평가
```

---

## 3. 제품 정의

### 3.1 한 문장 정의

> BOSSPROFIT은 시장 식재료 가격을 예측하고, 내 매장 원가와 판매 데이터를 연결해 평상시에는 사전 준비를 돕고 위기 상황에는 실행 전략을 함께 수립하는 AI 미니 ERP다.

### 3.2 제품의 세 축

#### A. 시장 전망

- KAMIS 농수산물 가격 현황
- 품목·지역·등급·도소매별 가격 추이
- 30·60·90일 가격 전망
- 급등·급락 품목
- 가격 변동 원인과 관련 사건

#### B. 내 매장 ERP

- 매장
- 재료와 실제 구매가격
- 메뉴와 레시피
- 일별 판매량
- 채널별 수수료
- 원가와 손익
- 행동계획과 실행 결과

#### C. AI 자영업 119

- 시장 사건 해석
- 내 매장 영향 분석
- 대안 비교
- 구체적 행동지침
- 성공·중단 기준 설정
- 과거 전략 회고

---

## 4. 핵심 제품 원칙

### 4.1 내부는 ERP, 외부 경험은 소비자 앱

데이터 구조는 ERP처럼 연결되어야 한다.

```text
시장가격
→ 내 구매가격
→ 재료
→ 레시피
→ 메뉴
→ 판매량
→ 손익
→ 예측
→ 행동계획
```

그러나 사용자는 ERP의 복잡함을 느껴서는 안 된다.

- 긴 테이블보다 요약과 다음 행동을 먼저 제공한다.
- 전문용어보다 사장님이 사용하는 말을 쓴다.
- 필수 입력과 선택 입력을 분리한다.
- 완료한 단계 뒤에 다음 단계를 공개한다.
- 한 화면에서 하나의 중요한 결정만 요구한다.

### 4.2 예측과 설명의 역할을 분리한다

- 정확한 숫자: SQL, 계산 엔진, ML 모델
- 과거 사례와 문서: RAG
- 설명과 전략 대화: LLM

LLM은 원가, 이익, 가격 전망을 임의로 계산하지 않는다.

### 4.3 데이터가 부족하면 솔직하게 말한다

30일 데이터만 가진 신규 매장에 개인 단위 통계적 유의성을 주장하지 않는다.

대신 다음을 표시한다.

- 사용한 데이터 기간
- 플랫폼 공통 학습 데이터 유무
- 예측 신뢰등급
- 80%·95% 예측구간
- 추가 데이터 입력 시 개선되는 항목

### 4.4 화면은 기능이 아니라 사용자 과업을 중심으로 설계한다

잘못된 메뉴명:

- 마스터 관리
- 손익 스냅샷
- 원가 가정
- 판매 데이터 CRUD

권장 메뉴명:

- 내 재료
- 메뉴 만들기
- 오늘 판매 입력
- 가격 전망
- 내 가게 영향
- 자영업 119

---

## 5. 핵심 사용자 여정

## 5.1 비로그인 사용자

```text
랜딩
→ 오늘의 식재료 시장 현황
→ 품목 가격 검색
→ 예측 기능 예시
→ 서비스 설명
→ 무료로 시작하기
```

비로그인 화면에서는 특정 샘플 매장의 매출·이익을 실제 사용자 데이터처럼 보여주지 않는다.

### 비로그인 핵심 화면

1. 랜딩
2. 시장가격 현황
3. 품목 상세
4. 로그인
5. 회원가입

## 5.2 회원가입

한 화면에 모든 항목을 노출하지 않는다.

```text
1단계: 아이디 또는 이메일
→ 성공
2단계: 비밀번호
→ 성공
3단계: 필수 약관
→ 성공
4단계: 가입 완료
```

다음 단계는 이전 단계가 유효할 때만 나타난다.

## 5.3 최초 로그인 온보딩

```text
1. 매장 등록
2. 첫 재료 등록
3. 첫 메뉴 등록
4. 레시피 구성
5. 최근 판매 데이터 입력
6. 첫 분석 생성
```

### 단계 공개 원칙

- 사용자가 저장하기 전에는 다음 단계의 세부 폼을 보여주지 않는다.
- 다음 단계가 있음을 작은 진행 표시로만 알려준다.
- 완료 시 현재 카드가 축소되고 다음 카드가 자연스럽게 확장된다.
- 사용자가 중단하면 마지막 완료 단계부터 재개한다.
- 선택 항목 때문에 핵심 흐름이 막혀서는 안 된다.

## 5.4 로그인 후 일상 사용

로그인 홈에는 다음만 노출한다.

1. 이번 달 예상 이익 또는 데이터 준비 상태
2. 오늘 가장 중요한 알림 한 개
3. 빠른 입력 세 개
   - 재료 가격 입력
   - 메뉴 추가
   - 판매량 입력
4. 가격 전망 또는 자영업 119 진입

나머지 세부 정보는 하위 화면으로 이동한다.

---

## 6. 정보구조

```text
공개
├─ 홈
├─ 식재료 시장
│  ├─ 시장 개요
│  └─ 품목 상세
├─ 서비스 소개
├─ 로그인
└─ 회원가입

내 매장
├─ 오늘
├─ 입력
│  ├─ 재료 가격 입력
│  ├─ 메뉴·레시피 등록
│  └─ 판매량 입력
├─ 관리
│  ├─ 내 재료
│  ├─ 메뉴
│  ├─ 구매 이력
│  └─ 판매 이력
├─ 분석
│  ├─ 손익
│  ├─ 식재료 영향
│  ├─ 30·60·90일 전망
│  └─ 시나리오 비교
└─ 자영업 119
   ├─ 대화
   ├─ 행동계획
   └─ 실행 결과
```

모바일 하단 내비게이션은 최대 4개로 제한한다.

```text
오늘 | 입력 | 시장 | 119
```

세부 ERP 메뉴는 `내 매장` 또는 더보기 화면에 둔다.

---

# 7. 팀 1: 프론트엔드·UI/UX 팀

## 7.1 팀의 문제의식

이 서비스의 사용자는 데이터 전문가가 아니다. 바쁜 영업 중 짧은 시간에 입력하고 판단해야 한다.

실패하기 쉬운 UX는 다음과 같다.

- 첫 화면부터 모든 KPI를 나열한다.
- 재료·메뉴 등록 경로가 숨겨져 있다.
- 한 화면에 긴 폼을 제공한다.
- 숫자와 표만 보여주고 다음 행동을 말하지 않는다.
- 아이콘 크기와 위치가 화면마다 다르다.
- 모바일에서 터치 영역이 작다.
- 저장 성공 여부를 사용자가 확신할 수 없다.
- 사용자가 입력을 마칠 때까지 아무 보상이 없다.

프론트엔드팀의 핵심 책임은 기능을 많이 보여주는 것이 아니라 사용자가 핵심 데이터를 끝까지 입력하도록 만드는 것이다.

## 7.2 핵심 기능

### A. 공개 랜딩

- 한 문장 가치 제안
- 식재료 시장 현황 미리보기
- 가격 전망 예시
- 자영업 119 대화 예시
- 무료 시작 CTA
- 로그인 CTA

### B. 회원가입·로그인

- 단계형 회원가입
- 비밀번호 표시 전환
- 실시간 유효성 검사
- 서버 오류를 필드 가까이에 표시
- 로그인 유지
- 토큰 만료 시 안전한 재로그인
- 로그아웃 확인 및 로컬 데이터 제거

### C. 최초 온보딩

- 단계 진행 상태
- 자동 저장
- 중단 후 재개
- 매장정보 입력
- 첫 재료 등록
- 첫 메뉴 등록
- 레시피 등록
- 판매량 입력
- 첫 분석 생성 애니메이션

### D. 재료 등록 마법사

```text
재료명 검색
→ KAMIS 품목 후보
→ 구매 단위
→ 실제 구매가격
→ 구매일
→ 공급처 선택 입력
→ 등록 완료
```

기능:

- 검색 자동완성
- KAMIS 연결 여부 표시
- 직접 입력 경로
- 단위 변환 미리보기
- 시장가격 대비 내 구매가격 표시
- 등록 완료 후 바로 다음 재료 추가
- 여러 재료를 연속 입력할 수 있는 흐름

### E. 메뉴·레시피 등록 마법사

```text
메뉴명·판매가
→ 등록 재료 선택
→ 재료별 사용량
→ 예상 원가 즉시 계산
→ 채널 조건
→ 저장
```

기능:

- 등록한 재료만 먼저 제안
- 자주 쓰는 재료 상단 배치
- 재료 추가 시 원가 실시간 갱신
- 목표 원가율 초과 시 즉시 안내
- 저장 전에 예상 마진 확인
- 첫 메뉴 이후 복제 등록

### F. 판매량 입력

- 오늘 판매량 빠른 입력
- 메뉴별 숫자 스테퍼
- 전일 값 불러오기
- CSV 업로드
- 오류 행 미리보기
- 저장 완료 요약

### G. 로그인 홈

노출 순서:

1. 데이터 준비 상태 또는 예상 이익
2. 가장 중요한 알림 한 개
3. 핵심 입력 CTA
4. 전망 또는 119 진입

### H. 시장가격 화면

- 전체 가격 지수
- 상승·하락 품목
- 품목 검색
- 지역·도매/소매·등급 필터
- 실제 가격과 예측 그래프
- 30·60·90일 토글
- 신뢰구간
- 데이터 기준일

### I. 자영업 119

- 채팅
- 추천 질문
- 사용한 데이터 근거 펼치기
- 계산 결과 카드
- 대안 비교
- 행동계획 저장
- 점검일 설정
- 과거 계획 조회

## 7.3 UI/UX 설계 규칙

### 정보 밀도

- 모바일 첫 화면의 주요 카드: 최대 3개
- 한 화면의 Primary CTA: 1개
- Secondary CTA: 최대 2개
- 한 카드의 핵심 숫자: 1개
- 한 카드의 설명 문장: 최대 2줄
- 표는 상세 화면에서만 사용

### 레이아웃

- 기본 4px 또는 8px spacing system
- 모바일 좌우 여백: 16px
- 데스크톱 콘텐츠 최대 폭: 1120~1200px
- 카드 내부 여백: 16px 또는 20px
- 섹션 간 간격: 모바일 32px, 데스크톱 48px
- 관련 요소 사이 간격: 8~12px
- 비관련 요소 사이 간격: 20px 이상

### 아이콘

- 한 프로젝트에서 하나의 아이콘 세트만 사용
- 문자 기호와 이모지를 주요 내비게이션 아이콘으로 사용하지 않는다.
- 기본 아이콘 canvas: 24×24px
- 실제 glyph 크기: 18~20px
- 모바일 터치 영역: 최소 44×44px
- 아이콘과 텍스트 간격: 8px
- 버튼 아이콘은 optical center를 기준으로 정렬
- 같은 레벨의 아이콘 stroke 두께를 통일
- 장식 아이콘과 기능 아이콘의 색을 구분
- 삭제·위험 동작에만 빨간색 사용

권장 아이콘:

- Lucide Icons 또는 Phosphor Icons 중 하나를 선정
- 프로젝트 중간에 혼용하지 않는다.

### 타이포그래피

- 본문 기본: 14~16px
- 보조 정보: 최소 12px
- 모바일 핵심 숫자: 24~32px
- 페이지 제목: 모바일 24~28px
- 한글 자간은 과도하게 벌리지 않는다.
- 숫자는 tabular-nums 사용
- 금액 단위는 숫자보다 시각적 위계를 낮춘다.

### 색상

- 브랜드 Primary 한 개
- Success, Warning, Danger 각 한 개
- 배경 단계 최대 3개
- 의미 없는 그라데이션 남용 금지
- 색만으로 상태를 전달하지 않고 텍스트·아이콘 병행
- WCAG AA 명암비 준수

### 폼

- 레이블은 입력창 위에 둔다.
- placeholder를 레이블 대신 사용하지 않는다.
- 필수와 선택 항목을 명확히 구분한다.
- 숫자 입력에는 단위를 항상 표시한다.
- 서버 오류를 상단 알림만으로 끝내지 않고 해당 필드에도 표시한다.
- 입력값 손실 없이 이전 단계로 이동할 수 있어야 한다.
- 모바일 숫자 입력에 적절한 inputmode를 사용한다.

### 애니메이션

목적 없는 장식 애니메이션은 금지한다.

허용 목적:

- 다음 단계 공개
- 저장 완료 피드백
- 데이터 로딩 상태
- 값 변화 강조
- 오류 위치 안내

규격:

- 일반 transition: 160~220ms
- 단계 전환: 240~320ms
- easing: ease-out 계열
- scale 효과: 0.98~1.00 범위
- 큰 이동보다 opacity와 8~16px 이동 사용
- `prefers-reduced-motion` 대응

### 상태 설계

모든 화면은 다음 상태를 설계해야 한다.

- 최초 빈 상태
- 로딩
- 부분 로딩
- 성공
- 저장 중
- 저장 완료
- 유효성 오류
- 서버 오류
- 네트워크 오류
- 권한 없음
- 데이터 부족
- 예측 신뢰도 낮음

## 7.4 핵심 기술

- Vue 3 Composition API
- TypeScript 전환
- Vite
- Pinia
- Vue Router
- Axios 또는 생성형 API client
- VueUse
- Zod 기반 프론트 유효성 검사
- Chart.js 또는 ECharts
- Lucide Vue 또는 Phosphor Vue
- CSS Variables + design token
- Storybook
- Vitest
- Vue Test Utils
- Playwright

Bootstrap은 점진적으로 제거한다. 디자인 시스템과 충돌하는 전역 스타일을 줄인다.

## 7.5 주요 산출물

- 사용자 여정 지도
- 저해상도 와이어프레임
- 고해상도 Figma
- 디자인 토큰
- 컴포넌트 라이브러리
- 아이콘 사용 규칙
- 모션 가이드
- 반응형 명세
- 접근성 체크리스트
- Playwright 핵심 여정 테스트

## 7.6 완료 기준

- 신규 사용자가 도움 없이 가입부터 첫 메뉴 분석까지 완료
- 모바일 360px 화면에서 가로 스크롤 없음
- 주요 CTA 터치 영역 44px 이상
- 폼 오류가 해당 입력 필드에 표시
- 새 재료 등록 평균 소요시간 60초 이내
- 첫 메뉴·레시피 등록 3분 이내
- Lighthouse Accessibility 90점 이상
- 핵심 여정 Playwright 테스트 통과
- 사용자 테스트 5명 중 4명 이상이 핵심 과업을 도움 없이 완료

## 7.7 기대효과

- 가입 중 이탈 감소
- 재료·메뉴 데이터 입력률 증가
- 사용자의 기능 탐색 비용 감소
- 신뢰감과 서비스 완성도 향상
- 예측 모델에 필요한 데이터 축적 가속

---

# 8. 팀 2: 백엔드·서비스 API 팀

## 8.1 팀의 문제의식

현재 구조는 메뉴와 재료가 전체 사용자 사이에서 공유되는 부분이 있어 실제 서비스의 멀티테넌트 요구를 충족하지 못한다.

또한 다음 문제가 해결되어야 한다.

- 인증과 매장 권한
- 단계형 온보딩 상태
- 원가 계산의 일관성
- 입력 이력과 감사 기록
- KAMIS 수집 작업 제어
- 예측 서버와 LLM 도구 연결
- 긴 작업의 비동기 처리

## 8.2 핵심 기능

### A. 인증·계정

- 이메일 또는 사용자명 회원가입
- 이메일 검증 확장 가능 구조
- 로그인
- access/refresh token
- refresh token rotation
- 로그아웃 시 토큰 폐기
- 비밀번호 재설정
- 로그인 시도 제한
- 계정 비활성화

### B. 매장·권한

- Store 생성
- StoreMember
- OWNER, MANAGER, STAFF 역할
- 모든 비즈니스 쿼리에 store scope 적용
- 다른 매장 데이터 접근 차단
- 향후 직원 초대 확장

### C. 온보딩

- 현재 단계 조회
- 단계별 저장
- 완료 조건 검증
- 중단 후 재개
- 단계 강제 순서
- 관리자용 단계 초기화

예시 상태:

```text
ACCOUNT_CREATED
STORE_CREATED
FIRST_INGREDIENT_CREATED
FIRST_MENU_CREATED
RECIPE_COMPLETED
SALES_DATA_ADDED
ANALYSIS_READY
```

### D. 재료·구매

- StoreIngredient CRUD
- KAMIS 품목 매핑
- PurchasePriceObservation CRUD
- 단위 변환
- 구매가격 이력
- 현재 가격 계산
- 시장가격 대비 프리미엄 계산

### E. 메뉴·레시피

- Menu CRUD
- RecipeItem transaction
- 중복 재료 방지
- 원가 즉시 계산
- 가격·레시피 변경 이력
- 메뉴 복제

### F. 판매

- DailyMenuSale CRUD
- 날짜·메뉴·채널 unique constraint
- bulk input
- CSV import
- 오류 행 반환
- idempotency key

### G. 손익·시나리오

- 현재 원가 계산
- 채널별 마진
- 월 예상 이익
- 재료가격 변화 시나리오
- 판매량 변화 시나리오
- 메뉴 가격 변화 시나리오
- 여러 대안 비교

### H. 예측 API 연결

- 예측 요청 생성
- ForecastRun 상태 조회
- 최신 예측 조회
- 모델 버전과 데이터 기준일 반환
- 신뢰구간 반환
- 예측 실패 fallback

### I. 자영업 119 도구 API

LLM이 직접 DB에 접근하지 않도록 허용 도구를 제공한다.

- `get_store_summary`
- `get_market_price_history`
- `get_market_forecast`
- `get_store_ingredient_impact`
- `get_menu_profitability`
- `simulate_cost_change`
- `simulate_sales_change`
- `search_knowledge`
- `create_action_plan`
- `review_action_plan`

### J. 행동계획

- 목표
- 배경
- 실행 항목
- 담당자
- 시작일
- 점검일
- 성공 기준
- 중단 기준
- 상태
- 실제 결과
- 연결된 AI 대화

## 8.3 API 설계 원칙

- `/api/v1` 버전 유지
- REST 우선
- OpenAPI 스키마 자동 생성
- serializer와 domain service 분리
- 계산 로직은 view에 두지 않는다.
- 모든 쓰기 API에 transaction 적용
- bulk API는 부분 성공 정책을 명시
- 오류 응답 형식을 통일
- request ID 포함
- 날짜는 ISO 8601
- 금액 저장은 정수 또는 Decimal
- 비율은 의미와 단위를 명확히 정의

표준 오류 예시:

```json
{
  "code": "INVALID_SALES_SHARE",
  "message": "홀·배달·포장 비중의 합은 100%여야 합니다.",
  "fields": {
    "delivery_share": ["판매 비중을 다시 확인해주세요."]
  },
  "request_id": "req_..."
}
```

## 8.4 핵심 기술

- Python 3.12+
- Django 5
- Django REST Framework
- PostgreSQL
- Redis
- Celery
- django-celery-beat
- SimpleJWT 또는 검증된 인증 패키지
- drf-spectacular
- Pydantic
- Sentry
- structlog
- pytest
- pytest-django
- factory_boy
- OpenTelemetry

## 8.5 서비스 계층

```text
API View
→ Serializer / Request Schema
→ Application Service
→ Domain Calculation
→ Repository / ORM
→ Event / Task
```

핵심 서비스 예시:

- `OnboardingService`
- `IngredientService`
- `RecipeService`
- `ProfitCalculationService`
- `ScenarioService`
- `ForecastGateway`
- `ChatOrchestrationService`
- `ActionPlanService`

## 8.6 보안

- 모든 리소스에 store scope
- object-level permission
- JWT rotation과 blacklist
- rate limiting
- CSRF/CORS 환경별 설정
- 운영 SECRET은 환경변수 또는 secret manager
- LLM prompt에 개인정보 최소화
- SQL 생성형 접근 금지
- 수정·삭제·발주 행동은 사용자 확인 필수
- 감사 로그

## 8.7 주요 산출물

- OpenAPI 문서
- 도메인 서비스
- 권한 매트릭스
- 비동기 작업 구조
- 에러 코드 목록
- API contract test
- 부하 테스트 시나리오
- 운영 로그·모니터링 대시보드

## 8.8 완료 기준

- 다른 매장의 데이터 접근 테스트 100% 차단
- 핵심 API 테스트 커버리지 80% 이상
- 일반 조회 API p95 500ms 이하
- 계산 API p95 1초 이하
- 비동기 작업 재시도와 실패 기록
- CSV 중복 업로드 시 데이터 중복 없음
- OpenAPI와 실제 응답 일치
- 예측 모델 장애 시 서비스 핵심 입력 기능 유지

## 8.9 기대효과

- 실제 서비스 수준의 사용자·매장 데이터 격리
- 프론트와 ML팀의 안정적인 계약
- 계산 결과의 재현성과 신뢰성 확보
- 운영 장애 진단 가능
- 향후 POS·결제·공급처 연동 기반 확보

---

# 9. 팀 3: DB·데이터 엔지니어링 팀

## 9.1 팀의 문제의식

예측과 RAG는 좋은 UI나 좋은 프롬프트만으로 만들 수 없다.

다음 조건이 충족되어야 한다.

- 시장 데이터가 매일 안정적으로 수집된다.
- 동일 품목의 이름과 단위가 정규화된다.
- 사용자 데이터와 시장 품목이 연결된다.
- 가격과 판매량의 이력이 삭제되지 않는다.
- 누락·중복·이상치가 관리된다.
- 모델이 동일한 기준으로 데이터를 재현할 수 있다.

## 9.2 핵심 데이터 영역

### A. 계정·매장

- User
- Store
- StoreMember
- StoreProfile
- StoreOperatingCondition
- OnboardingProgress

### B. 시장 품목

- MarketCategory
- MarketItem
- MarketVariety
- MarketGrade
- MarketRegion
- MarketUnit
- MarketItemMapping

### C. 시장가격

- MarketPriceObservation
- MarketPriceIngestionRun
- MarketPriceQualityIssue
- MarketPriceAdjustment

권장 unique:

```text
source
observation_date
item
variety
grade
region
market_type
unit
```

### D. 매장 재료

- StoreIngredient
- StoreIngredientMarketMapping
- Supplier
- PurchasePriceObservation
- UnitConversion

### E. 메뉴와 판매

- Menu
- RecipeItem
- MenuPriceHistory
- RecipeVersion
- DailyMenuSale
- SalesImportRun
- SalesImportError

### F. 예측

- FeatureSnapshot
- ForecastRun
- ForecastPoint
- ForecastMetric
- ModelRegistry
- ModelTrainingRun
- DriftReport

### G. RAG·119

- KnowledgeSource
- KnowledgeDocument
- KnowledgeChunk
- DocumentEmbedding
- ChatThread
- ChatMessage
- ToolExecutionLog
- ActionPlan
- ActionPlanItem
- ActionPlanReview

## 9.3 저장 기술

### 운영 DB

PostgreSQL을 사용한다.

이유:

- 관계형 ERP 데이터
- transaction
- 복잡한 집계
- JSONB
- row-level security 확장 가능
- pgvector 결합 가능

### Vector 저장

초기에는 PostgreSQL + pgvector를 사용한다.

벡터 DB를 별도로 분리하는 시점:

- chunk 수가 수백만 단위를 넘어감
- 검색 latency 요구를 충족하지 못함
- 독립적인 scaling이 필요함

### 캐시와 큐

- Redis

### 파일 저장

- CSV 원본
- 보고서 원본
- 뉴스·공공 문서 원본
- 모델 artifact

개발: 로컬 또는 MinIO  
운영: S3 호환 object storage

## 9.4 KAMIS 수집 파이프라인

```text
스케줄 시작
→ API 요청
→ raw response 저장
→ schema 검증
→ 품목·단위 정규화
→ 중복 제거
→ observation upsert
→ 품질 검사
→ 집계 갱신
→ 모델 feature 갱신
→ 완료 알림
```

### 수집 요구사항

- 인증키 환경변수 관리
- API 제한 준수
- 날짜별 증분 수집
- 최근 N일 재수집으로 수정 데이터 반영
- exponential backoff
- 실패 구간 재처리
- source payload 보존
- ingestion run ID

### 품질 검사

- 필수 필드 누락
- 중복
- 단위 불일치
- 가격 0 또는 음수
- 전일 대비 비정상 급등락
- 장기간 동일값
- 품목 매핑 실패
- 지역 코드 불일치

급등락 데이터는 자동 삭제하지 않는다. 실제 사건일 수 있으므로 품질 플래그를 부여하고 검토한다.

## 9.5 외부 변수

예측 성능을 위해 다음 데이터를 단계적으로 수집한다.

- 기상청 기온·강수·습도·폭염·한파
- 공휴일
- 환율
- 유가
- 국제 곡물·원자재 가격
- 물류 관련 지표
- 수급 보고서
- 국제 사건 메타데이터

각 데이터에는 다음을 저장한다.

- source
- 수집 시각
- 관측 기준 시각
- 수정 여부
- 라이선스
- 원본 URL 또는 식별자

## 9.6 데이터 계약

각 테이블·이벤트·API 필드에 다음을 정의한다.

- 필드명
- 의미
- 타입
- 단위
- nullable
- source
- 갱신 주기
- owner team

예:

```text
market_price
- 의미: 표준단위당 시장가격
- 타입: NUMERIC(14, 4)
- 통화: KRW
- 기준단위: market_unit_id 참조
- owner: DB·데이터팀
```

## 9.7 단위 정규화

원가 계산의 핵심 위험이다.

예:

```text
시장: 양파 20kg 망
내 구매: 양파 15kg 박스
레시피: 양파 80g
```

모든 가격은 표준단위 가격으로 변환 가능해야 한다.

- 질량: g
- 부피: ml
- 개수: ea

변환이 불가능한 단위는 강제로 환산하지 않고 사용자 확인을 요청한다.

## 9.8 RAG 데이터화

Vector DB 대상:

- KAMIS 시장 동향 보고서
- 정부 수급 보고서
- 기상 영향 보고서
- 국제 원자재·분쟁 분석
- 과거 가격 급등 사례 요약
- 외식업 운영 가이드
- 과거 AI 상담 요약
- 실행 전략과 결과

정형 가격 행을 그대로 임베딩하지 않는다.

정형 가격은 SQL 시계열 조회에 사용하고, 다음과 같은 요약 문서를 생성해 임베딩한다.

```text
기준일
품목
지역
최근 7·30·90일 변화
변동성
관련 외부 요인
급등락 여부
출처
```

## 9.9 핵심 기술

- PostgreSQL
- pgvector
- Redis
- Celery Beat 또는 Airflow
- dbt
- Pandas 또는 Polars
- Great Expectations 또는 Pandera
- MinIO/S3
- Docker
- Metabase 또는 Superset

초기에는 Celery 기반 수집으로 시작하고 파이프라인이 복잡해지면 Airflow로 이전할 수 있다.

## 9.10 주요 산출물

- ERD
- 데이터 사전
- source-to-target mapping
- KAMIS 수집기
- 품질 규칙
- 단위 변환 테이블
- 데이터 lineage
- 백업·복구 정책
- 모델 학습용 feature dataset

## 9.11 완료 기준

- 일별 KAMIS 수집 성공률 99% 이상
- 동일 데이터 재수집 시 중복 없음
- 수집 실패 감지 10분 이내
- 모든 시장가격에 source와 기준일 존재
- 내 재료와 시장 품목 매핑률 측정 가능
- 원가 계산에 사용한 단위를 추적 가능
- 모델 학습 데이터셋을 동일 조건으로 재생성 가능
- 개인정보와 매장 데이터 백업·복구 검증

## 9.12 기대효과

- 예측 가능한 데이터 기반 확보
- 사용자 구매가격과 시장가격 비교
- 과거 유사 상황 검색
- 모델 재현성과 감사 가능성
- 장기적으로 축적되는 서비스 고유 데이터 자산 형성

---

# 10. 팀 4: ML·예측·RAG·LLM 팀

## 10.1 팀의 문제의식

AI가 있다는 사실보다 중요한 것은 다음이다.

- 기준 모델보다 실제로 나은가?
- 어느 기간에서 잘 작동하는가?
- 불확실성을 표시하는가?
- 예측 근거를 설명할 수 있는가?
- 갑작스러운 사건에 대해 숫자를 날조하지 않는가?
- 내 매장 데이터를 사용했는지 확인할 수 있는가?

## 10.2 가격 예측

### 목표

- 품목별 7·30·60·90일 가격 예측
- 중앙값
- 80%·95% 예측구간
- 신뢰등급
- 주요 영향 요인

### 기준 모델

- 마지막 값 유지
- 계절 나이브
- 이동평균
- ETS

### 1차 운영 후보

#### SARIMAX

역할:

- 추세와 자기상관
- 계절성
- 기상·환율·유가 등 외생변수
- 통계 계수와 신뢰구간

장점:

- 설명 가능성
- 비교적 적은 데이터에서도 학습
- baseline 이상의 통계 모델

한계:

- 복잡한 비선형 상호작용
- 품목 수가 많을 때 개별 관리 비용

#### LightGBM Quantile

역할:

- lag와 rolling feature
- 날씨·지역·품목·등급
- 비선형 상호작용
- 분위수 예측

장점:

- 다양한 외생변수
- 비교적 빠른 학습
- SHAP 설명
- global model 구성

### 앙상블

품목별 rolling backtest 성능에 따라 가중치를 결정한다.

```text
최종 예측
= SARIMAX 예측 × 품목별 가중치
+ LightGBM 예측 × 품목별 가중치
```

가중치는 테스트 구간을 보면서 임의로 정하지 않는다. validation 구간에서 고정하고 test 구간에 적용한다.

## 10.3 메뉴 판매량 예측

### 1차 모델

LightGBM Quantile Global Model

### 특징

- lag 1·7·14·28
- rolling mean 7·14·28
- rolling std
- 요일·주말·공휴일
- 메뉴 가격
- 가격 변경
- 카테고리
- 날씨
- 관련 재료 가격 지수
- 채널
- 매장·메뉴 embedding 또는 category encoding

### cold-start

30일 데이터 신규 매장:

- 유사 카테고리·지역·가격대의 global model prior
- 매장 최근 30일 특성
- 넓은 예측구간
- 낮은 신뢰도 표시

플랫폼 공통 데이터가 충분하지 않다면 60·90일은 시나리오 수준으로 제공한다.

## 10.4 딥러닝 도입 조건

Temporal Fusion Transformer 또는 다른 deep forecasting model은 다음 조건 후 검토한다.

- 관련 시계열 수백 개 이상
- 시계열당 충분한 길이
- 외생변수 품질 안정
- baseline과 tree model을 유의미하게 개선
- 운영 inference 비용 허용

딥러닝이라는 이유만으로 채택하지 않는다.

## 10.5 통계적 검증

### 분할

무작위 train/test split 금지.

- rolling-origin evaluation
- expanding window 또는 sliding window
- 7·30·60·90일 horizon 별 평가

### 지표

- WAPE
- MASE
- RMSSE
- Pinball loss
- interval coverage
- interval width
- bias

### 유의성

- Diebold–Mariano test
- paired bootstrap 95% CI
- 다수 품목 검정 시 Holm correction

운영 모델 채택 기준:

- baseline 대비 WAPE 또는 MASE 개선
- 예측구간 coverage 목표 충족
- 개선 신뢰구간이 0을 넘음
- 주요 품목에서 치명적 성능 저하 없음

## 10.6 예측 신뢰등급

예:

```text
높음
- 충분한 이력
- 최근 데이터 정상
- backtest 안정

보통
- 일부 외생변수 누락
- 중간 수준 변동성

낮음
- 데이터 30일 미만
- 최근 구조적 변화
- 극단 사건
- 예측구간 과도하게 넓음
```

## 10.7 RAG

### 목적

RAG는 숫자 계산이 아니라 다음을 담당한다.

- 가격 변동 원인
- 과거 유사 사건
- 정부·시장 보고서
- 운영 대응 사례
- 과거 상담과 실행 결과

### 검색

Hybrid retrieval:

- metadata filtering
- dense vector search
- keyword/BM25
- reranking

필수 metadata:

- source
- published_at
- valid_from
- item
- region
- event_type
- reliability
- document_version

### chunking

- 문서 구조 기반
- 표와 본문 분리
- 출처와 날짜 유지
- 문맥 없는 짧은 chunk 금지
- 중복 문서 제거

### 답변 근거

- 검색 문서 제목
- 출처
- 기준일
- 사용한 매장 데이터 기간
- 예측 모델 버전
- 예측구간

## 10.8 LLM 자영업 119

### 역할

- 질문 의도 분류
- 필요한 도구 선택
- 결과 종합
- 대안 생성
- 실행계획 작성
- 후속 질문

### 금지

- 임의 숫자 생성
- 직접 SQL 실행
- 다른 매장 데이터 접근
- 출처 없는 사건 단정
- 사용자의 확인 없는 데이터 수정
- 예측구간을 확정값처럼 표현

### 응답 구조

```text
1. 지금 상황
2. 내 매장 영향
3. 예상 범위
4. 오늘 할 일
5. 1주 안에 할 일
6. 선택 가능한 대안
7. 성공 기준
8. 중단 기준
9. 근거와 신뢰도
```

### LLM 선택

실시간 대화:

- 빠르고 비용 효율적인 tool-calling 지원 모델
- 현재 후보: GPT-5.4 mini
- 실제 채택 전 한국어 전략 답변, tool 선택 정확도, latency, 비용을 평가

복잡한 보고서:

- 상위 추론 모델을 비동기로 사용 가능
- 현재 후보: GPT-5.5

모델 ID는 코드에 하드코딩하지 않고 환경설정과 ModelRegistry로 관리한다.

## 10.9 행동계획 학습 루프

AI 제안을 저장하는 것만으로 끝내지 않는다.

```text
권고
→ 사용자 선택
→ 실행
→ 점검
→ 실제 결과
→ 전략 평가
→ 유사 상황 검색 자산
```

성과:

- 예상 절감액
- 실제 절감액
- 판매량 변화
- 마진 변화
- 사용자 평가

과거 전략은 RAG 지식으로 재활용할 수 있지만 매장 간 공유 시 반드시 비식별·집계 처리한다.

## 10.10 핵심 기술

- Python
- Pandas 또는 Polars
- scikit-learn
- LightGBM
- statsmodels
- Optuna
- SHAP
- MLflow
- Feast 선택 검토
- FastAPI 모델 서버
- PostgreSQL + pgvector
- sentence-transformers 또는 embedding API
- OpenAI Responses API 또는 동등한 tool-calling API
- RAGAS 또는 자체 평가셋
- Evidently 또는 자체 drift monitoring

## 10.11 평가셋

### 예측

- 품목별 시계열
- 급등락 구간
- 계절 전환
- 외생 충격
- 데이터 누락

### RAG

- 정답 문서 존재
- 유사 문서 혼재
- 오래된 문서
- 지역·품목 필터
- 답변 불가능 질문

### LLM

- 도구 선택
- 매장 scope
- 숫자 복사 정확도
- 근거 포함
- 과도한 확신 방지
- 행동계획 구체성
- 한국어 자연스러움

## 10.12 완료 기준

- baseline과 비교한 backtest 보고서
- 모델 버전 추적
- 모든 예측에 기준일·구간·신뢰도
- RAG 근거 문서 추적
- LLM 숫자 일치 평가 99% 이상
- 다른 매장 데이터 노출 0건
- 답변 불가능 상황에서 안전한 거절
- 자영업 119 핵심 평가셋 통과

## 10.13 기대효과

- 단순 정보 제공이 아닌 선제적 의사결정
- 시장 변화와 내 매장 데이터 연결
- 갑작스러운 사건에 대한 빠른 대응
- 서비스 사용 과정에서 축적되는 전략 지식
- 일반 ERP와 차별화되는 AI 경영 코치

---

# 11. 팀 간 계약

## 11.1 프론트 ↔ 백엔드

- OpenAPI를 단일 계약으로 사용
- 임의 응답 필드 추가 금지
- 오류 코드 합의
- loading·empty·error 상태를 API 명세에 포함
- pagination과 sorting 통일

## 11.2 백엔드 ↔ DB

- migration review
- 데이터 owner 지정
- 인덱스와 unique constraint 합의
- soft delete 정책
- 이력 테이블 정책

## 11.3 DB ↔ ML

- feature definition
- point-in-time correctness
- 데이터 기준일
- 학습·검증 데이터 snapshot
- label leakage 검사

## 11.4 백엔드 ↔ ML

예측 응답 최소 형식:

```json
{
  "target_type": "market_price",
  "target_id": "ITEM_ONION",
  "as_of": "2026-06-24",
  "horizon_days": 30,
  "median": 1850,
  "lower_80": 1650,
  "upper_80": 2050,
  "lower_95": 1500,
  "upper_95": 2250,
  "confidence": "MEDIUM",
  "model_version": "market-price-2026-06-01",
  "data_quality": []
}
```

## 11.5 LLM tool ↔ 백엔드

- JSON schema
- read-only와 write tool 분리
- write tool은 confirmation token 필요
- tool execution log
- timeout과 fallback

---

# 12. 통합 기술 스택

| 영역 | 권장 기술 |
|---|---|
| Frontend | Vue 3, TypeScript, Vite, Pinia, Vue Router |
| UI | CSS tokens, Storybook, Lucide/Phosphor |
| Front Test | Vitest, Vue Test Utils, Playwright |
| Backend | Django, DRF, Celery, Redis |
| API | REST, OpenAPI, drf-spectacular |
| DB | PostgreSQL |
| Vector | pgvector |
| Object Storage | S3/MinIO |
| Data Pipeline | Celery Beat → 필요 시 Airflow |
| Data Quality | Pandera/Great Expectations |
| ML | LightGBM, statsmodels, scikit-learn |
| ML Tracking | MLflow |
| ML Serving | FastAPI |
| LLM | Tool-calling LLM, provider abstraction |
| Monitoring | Sentry, OpenTelemetry, Grafana |
| Infra | Docker, CI/CD, managed PostgreSQL |

---

# 13. 단계별 개발 로드맵

## Phase 0. 제품·UX 기준

- 사용자 인터뷰 5명 이상
- 핵심 과업 정의
- 정보구조
- Figma flow
- 디자인 토큰
- API·ERD 초안

완료 조건:

- 가입부터 첫 분석까지 clickable prototype
- 네 팀 계약 승인

## Phase 1. ERP 기반

- Store 멀티테넌트
- 인증
- 단계형 온보딩
- 재료·구매가격
- 메뉴·레시피
- 판매량

완료 조건:

- 신규 사용자가 자신의 데이터로 원가 계산 완료

## Phase 2. 시장 데이터

- KAMIS 수집
- 시장가격 화면
- 내 구매가격 비교
- 데이터 품질 모니터링

완료 조건:

- 매일 자동 수집
- 품목 상세 조회
- 내 재료 매핑

## Phase 3. 예측

- baseline
- SARIMAX
- LightGBM Quantile
- backtest
- 예측 API
- 신뢰구간 UI

완료 조건:

- 기준 모델 대비 검증
- 30·60·90일 화면

## Phase 4. 자영업 119

- 문서 ingestion
- pgvector
- hybrid retrieval
- LLM tool orchestration
- 행동계획
- 근거 표시

완료 조건:

- 시장 사건 질문
- 내 매장 영향 계산
- 행동계획 저장

## Phase 5. 운영 고도화

- POS 연동
- 공급처
- 알림
- 모델 drift
- 전략 결과 학습
- 직원 권한

---

# 14. MVP 범위

## 반드시 포함

- 회원가입·로그인·로그아웃
- Store 데이터 격리
- 단계형 온보딩
- 재료와 구매가격
- 메뉴와 레시피
- 판매량 입력
- KAMIS 시장가격
- 기본 가격 예측
- 내 메뉴 영향 계산
- 근거 기반 자영업 119

## 제외

- 회계 전표
- 세무 신고
- 급여·근태
- 복잡한 창고 WMS
- 전자결재
- 모든 POS 동시 연동
- 자동 발주 실행
- 설명할 수 없는 딥러닝 우선 도입

---

# 15. 제품 성과지표

## 활성화

- 가입 완료율
- 매장 등록 완료율
- 첫 재료 등록률
- 첫 메뉴 등록률
- 첫 분석 도달률
- 가입 후 첫 분석까지 걸린 시간

## 데이터

- 사용자당 등록 재료 수
- 사용자당 등록 메뉴 수
- 판매량 입력 일수
- KAMIS 매핑률
- 구매가격 갱신률

## 예측

- WAPE
- MASE
- interval coverage
- 예측 조회율
- 예측 기반 행동계획 생성률

## 자영업 119

- 질문 후 행동계획 저장률
- 실행 완료율
- 사용자 평가
- 근거 펼쳐보기 비율
- 잘못된 숫자 또는 출처 신고율

## UX

- 핵심 과업 완료율
- 과업별 소요시간
- 폼 이탈률
- 오류 발생률
- 재입력률
- 모바일 사용률

---

# 16. 주요 리스크와 대응

## 데이터 부족

대응:

- baseline 우선
- global model
- 신뢰도 낮음 표시
- 추가 입력 유도

## KAMIS 품목과 실제 구매품 불일치

대응:

- 다대다 매핑
- 단위 변환
- 사용자 확인
- 매핑 신뢰도

## 외부 사건의 허위 해석

대응:

- 신뢰 가능한 출처 allowlist
- 날짜·출처 표시
- 복수 출처
- 답변 불가능 처리

## LLM 숫자 환각

대응:

- tool output만 사용
- structured output
- 숫자 일치 검사
- post-validation

## UI 과밀

대응:

- 홈 카드 최대 수
- progressive disclosure
- 핵심 CTA 1개
- 사용자 테스트

## 범위 폭발

대응:

- 가격 예측과 위기 대응에 직접 필요한 ERP만 구현
- 세무·급여·전자결재 제외

---

# 17. 최종 기대효과

### 사용자

- 가격이 오른 뒤 당황하는 대신 미리 준비한다.
- 시장 정보가 내 매장에 어떤 의미인지 이해한다.
- 메뉴 가격을 바로 올리지 않고도 대안을 비교한다.
- 국제 사건과 수급 위기에 구체적으로 대응한다.
- 실행한 전략의 효과를 기록하고 회고한다.

### 서비스

- 일반 원가 계산기와 차별화
- ERP 데이터가 예측 성능을 개선
- 예측 결과가 AI 대화의 근거가 됨
- 대화와 행동 결과가 서비스 고유 지식으로 축적
- 장기적으로 자영업 의사결정 플랫폼으로 확장

---

# 18. 최종 개발 원칙

1. 사용자가 데이터를 넣지 못하면 AI도 존재하지 않는 것과 같다.
2. 입력 경험은 분석 화면보다 먼저 완성한다.
3. 홈은 모든 정보를 보여주는 곳이 아니라 다음 행동을 알려주는 곳이다.
4. 숫자는 DB·계산·ML이 만들고 LLM은 설명한다.
5. 예측은 확정값이 아니라 범위와 신뢰도로 제시한다.
6. RAG는 과거 상황과 운영 지식을 검색한다.
7. 모든 데이터는 매장 단위로 격리한다.
8. 모든 주요 AI 답변은 근거와 기준일을 제공한다.
9. 딥러닝은 데이터와 검증 결과가 정당화할 때만 도입한다.
10. UI의 간격, 아이콘, 상태, 애니메이션도 기능 명세의 일부로 취급한다.

