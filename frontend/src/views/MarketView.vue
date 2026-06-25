<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import BossPersona from '@/components/BossPersona.vue'

const router = useRouter()
const activeScope = ref('briefing')
const searchQuery = ref('')

function searchItem() {
  router.push({
    name: 'MarketRanking',
    params: { type: 'tomorrow' },
    query: searchQuery.value.trim() ? { q: searchQuery.value.trim() } : {},
  })
}

const annualConsumption = [
  { rank: 1, name: '양파', value: '연동 후 표시', unit: 'kg/인·년' },
  { rank: 2, name: '배추', value: '연동 후 표시', unit: 'kg/인·년' },
  { rank: 3, name: '무', value: '연동 후 표시', unit: 'kg/인·년' },
]

const marketSignals = [
  {
    key: 'volume',
    eyebrow: '실시간 대리 지표',
    title: '거래량 TOP 5',
    description: '전국 공영도매시장 거래량·반입량',
    rows: ['양파', '배추', '대파', '감자', '마늘'],
    unit: '톤',
    tone: 'sage',
  },
  {
    key: 'today',
    eyebrow: '오늘 시장',
    title: '가격 변동 TOP 5',
    description: '직전 유효 거래일 대비 절대 등락률',
    rows: ['마늘', '양파', '배추', '대파', '감자'],
    unit: '%',
    tone: 'amber',
  },
  {
    key: 'tomorrow',
    eyebrow: 'AI 가격 전망',
    title: '내일 예상 변동 TOP 5',
    description: '내일 중앙 예측값 기준 예상 등락률',
    rows: ['양파', '대파', '감자', '배추', '마늘'],
    unit: '%',
    tone: 'terracotta',
  },
]

const sources = [
  {
    label: '공식 소비 수준',
    name: 'KOSIS 식품수급 통계',
    cadence: '연간',
    usage: '1인당 공급량과 장기 소비 구조',
    status: 'API 키 필요',
    href: 'https://kosis.kr/openapi/index/index.jsp',
  },
  {
    label: '구매 행동',
    name: '농식품 소비자패널',
    cadence: '월·연',
    usage: '가구 구매량·구매빈도 분석',
    status: '제공 범위 확인',
    href: 'https://www.rda.go.kr/',
  },
  {
    label: '일별 시장 신호',
    name: '전국 공영도매시장 실시간 경매정보',
    cadence: '실시간',
    usage: '거래량·반입량 기반 수요 대리 지표',
    status: '활용신청 필요',
    href: 'https://www.data.go.kr/data/15141808/openapi.do',
  },
]
</script>

<template>
  <div class="market-page">
    <section class="market-hero">
      <div>
        <span class="section-kicker">MARKET INTELLIGENCE</span>
        <h1>시장 흐름을<br>먼저 읽습니다.</h1>
        <p>소비 구조, 오늘의 거래량, 내일의 가격 변화를 한곳에서 확인하세요.</p>
      </div>
      <div class="market-hero-persona">
        <div class="market-hero-persona-pair" aria-label="시장 분석을 함께하는 남녀 사장님 페르소나">
          <BossPersona persona="female" alt="" />
          <BossPersona persona="male" alt="" />
        </div>
        <div>
          <span>오늘의 시장 브리핑</span>
          <strong>데이터 연결 준비 중</strong>
          <small>현재 화면은 실제 연동 전 UI 시제품입니다.</small>
        </div>
      </div>
    </section>

    <nav class="market-scope-tabs" aria-label="시장 데이터 보기">
      <button :class="{ active: activeScope === 'briefing' }" @click="activeScope = 'briefing'">시장 브리핑</button>
      <button :class="{ active: activeScope === 'consumption' }" @click="activeScope = 'consumption'">소비량</button>
      <button :class="{ active: activeScope === 'sources' }" @click="activeScope = 'sources'">데이터 출처</button>
    </nav>

    <template v-if="activeScope === 'briefing'">
      <form class="market-search" @submit.prevent="searchItem">
        <span>품목 검색</span>
        <input v-model="searchQuery" placeholder="양파, 배추, 대파..." aria-label="시장 품목 검색">
        <button>검색</button>
      </form>

      <section class="market-signal-grid">
        <button
          v-for="signal in marketSignals"
          :key="signal.key"
          class="market-signal-card"
          :class="signal.tone"
          @click="$router.push(`/market/rankings/${signal.key}`)"
        >
          <div class="market-card-heading">
            <span>{{ signal.eyebrow }}</span>
            <small>UI 예시</small>
          </div>
          <h2>{{ signal.title }}</h2>
          <p>{{ signal.description }}</p>
          <ol>
            <li v-for="(item, index) in signal.rows" :key="item">
              <b>{{ index + 1 }}</b>
              <strong>{{ item }}</strong>
              <span>-- {{ signal.unit }}</span>
            </li>
          </ol>
          <footer>기준일·단위·출처가 연동 후 표시됩니다.</footer>
        </button>
      </section>
    </template>

    <section v-else-if="activeScope === 'consumption'" class="consumption-prototype">
      <div class="consumption-heading">
        <div>
          <span class="section-kicker">ANNUAL CONSUMPTION</span>
          <h2>많이 소비되는 농산물</h2>
          <p>공식 연간 통계가 연결되면 1인당 공급량과 연도별 변화를 표시합니다.</p>
        </div>
        <span class="prototype-badge">연동 전 형태</span>
      </div>

      <div class="consumption-ranking">
        <article v-for="item in annualConsumption" :key="item.name">
          <span>{{ item.rank }}</span>
          <div>
            <strong>{{ item.name }}</strong>
            <small>전국 기준</small>
          </div>
          <p>{{ item.value }} <small>{{ item.unit }}</small></p>
        </article>
      </div>

      <div class="consumption-definition">
        <strong>소비량은 이렇게 구분합니다.</strong>
        <div>
          <p><b>공식 소비 수준</b><span>식품수급표·국가통계의 연간 1인당 공급량</span></p>
          <p><b>구매 소비</b><span>소비자패널의 가구 구매량과 구매빈도</span></p>
          <p><b>일별 대리 지표</b><span>도매시장 거래량·반입량이며 소비량으로 부르지 않음</span></p>
        </div>
      </div>
    </section>

    <section v-else class="market-source-panel">
      <div class="consumption-heading">
        <div>
          <span class="section-kicker">DATA SOURCES</span>
          <h2>소비량 데이터 연결 계획</h2>
          <p>갱신 주기와 의미가 다른 데이터를 한 순위로 섞지 않습니다.</p>
        </div>
      </div>
      <div class="market-source-list">
        <a v-for="source in sources" :key="source.name" :href="source.href" target="_blank" rel="noreferrer">
          <span>{{ source.label }}</span>
          <div>
            <strong>{{ source.name }}</strong>
            <p>{{ source.usage }}</p>
          </div>
          <small>{{ source.cadence }}</small>
          <b>{{ source.status }}</b>
        </a>
      </div>
    </section>
  </div>
</template>
