# BOSS PROFIT - 메뉴 원가 관리 API

식당 메뉴의 판매가, 재료 단가, 레시피 사용량을 관계형 DB로 관리하고 메뉴별 원가와 마진을 계산하는 REST API 프로젝트입니다.

기존 Django 기반 BOSSPROFIT MVP에서 확인한 메뉴 원가 계산 구조를 바탕으로, TypeScript, Express, Prisma, SQLite를 사용해 서버 API로 재구현했습니다.

## 기술 환경

- TypeScript
- Node.js
- Express
- Prisma ORM
- SQLite

## 프로젝트 목표

- 메뉴, 재료, 레시피 항목을 관계형 DB 테이블로 분리
- 메뉴와 재료의 다대다 관계를 `RecipeItem` 중간 테이블로 표현
- `quantity`를 기반으로 메뉴별 총 원가와 마진 계산
- REST API로 메뉴, 재료, 레시피, 원가 계산 결과 제공
- HTML 화면으로 API 결과와 DB 구조 확인

## DB 설계

### Menu

판매 메뉴를 저장합니다.

- `id`: 메뉴 PK
- `name`: 메뉴명
- `category`: 카테고리
- `price`: 판매가

### Ingredient

재료 단가 정보를 저장합니다.

- `id`: 재료 PK
- `name`: 재료명
- `unit`: 단위
- `unitPrice`: 단위당 가격

### RecipeItem

메뉴와 재료를 연결하는 중간 테이블입니다.

- `id`: 레시피 항목 PK
- `menuId`: Menu FK
- `ingredientId`: Ingredient FK
- `quantity`: 해당 메뉴에 들어가는 재료 사용량

`Menu`와 `Ingredient`는 다대다에 가까운 관계입니다. 하나의 메뉴에는 여러 재료가 들어가고, 하나의 재료는 여러 메뉴에 사용될 수 있습니다. 단순 Many-to-Many 구조만 사용하면 메뉴별 재료 사용량을 저장하기 어렵기 때문에 `RecipeItem` 테이블을 직접 설계했습니다.

## 화면

API 결과 화면:

```text
http://localhost:3000
```

DB 구조 화면:

```text
http://localhost:3000/schema.html
```

## API 목록

| Method | URL | 설명 |
|---|---|---|
| GET | `/api/menus` | 메뉴 목록 조회 |
| GET | `/api/menus/:id` | 메뉴 상세 조회 |
| GET | `/api/menus/:id/cost` | 메뉴별 원가 계산 |
| GET | `/api/ingredients` | 재료 목록 조회 |
| GET | `/api/recipe-items` | 레시피 항목 조회 |
| POST | `/api/recipe-items` | 레시피 항목 등록 |

## 원가 계산 응답 예시

`GET /api/menus/1/cost`

```json
{
  "menu": "왕돈까스",
  "price": 13000,
  "total_cost": 1860,
  "margin": 11140,
  "margin_rate": 85.69,
  "items": [
    {
      "ingredient": "돼지고기",
      "quantity": 200,
      "unit": "g",
      "unit_price": 7,
      "cost": 1400
    }
  ]
}
```

## 실행 방법

```bash
npm install
copy .env.example .env
npx prisma generate
npx prisma migrate dev --name init
npm run seed
npm run dev
```

Windows 로컬 환경에서 Prisma schema engine 오류로 마이그레이션이 실패하면 아래 순서로 SQLite 테이블을 직접 생성할 수 있습니다.

```bash
npm run db:create
npx prisma generate
npm run seed
npm run dev
```

서버 실행 후 아래 주소에서 확인합니다.

```text
http://localhost:3000
http://localhost:3000/schema.html
http://localhost:3000/api/menus
http://localhost:3000/api/menus/1/cost
```

## 샘플 데이터

### Menu

- 왕돈까스 / 돈까스 / 13000
- 치즈돈까스 / 돈까스 / 15000
- 즉석우동 / 우동 / 8000
- 어묵우동 / 우동 / 9000

### Ingredient

- 돼지고기 / g / 7
- 빵가루 / g / 3.25
- 치즈 / g / 23.8
- 식용유 / ml / 2
- 우동면 / 개 / 800
- 어묵 / 개 / 500
- 우동육수 / ml / 1.5

## 구현 포인트

- `RecipeItem`을 중간 테이블로 두어 메뉴별 재료 사용량을 저장했습니다.
- Prisma relation을 사용해 `Menu -> RecipeItem -> Ingredient` 관계를 조회했습니다.
- 원가 계산 로직은 `src/services/cost.service.ts`로 분리했습니다.
- API 라우트는 메뉴, 재료, 레시피 항목 단위로 분리했습니다.
- `public/schema.html`에서 DB 구조를 시각적으로 확인할 수 있도록 했습니다.

## 폴더 구조

```text
boss-profit-api-ts/
├── docs/
│   └── db-schema.md
├── prisma/
│   └── schema.prisma
├── public/
│   ├── index.html
│   └── schema.html
├── scripts/
│   └── create_sqlite_db.py
├── src/
│   ├── app.ts
│   ├── prisma.ts
│   ├── seed.ts
│   ├── routes/
│   │   ├── ingredient.routes.ts
│   │   ├── menu.routes.ts
│   │   └── recipe-item.routes.ts
│   └── services/
│       └── cost.service.ts
├── package.json
├── tsconfig.json
├── .env.example
└── README.md
```
