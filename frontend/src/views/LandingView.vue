<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { fetchPublicPreview } from '@/api/endpoints'
import heroImage from '@/assets/illustrations/bossprofit-hero.png'
import { produceImages } from '@/utils/productAssets'
import { formatKRW } from '@/utils/format'

const authStore = useAuthStore()
const preview = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await fetchPublicPreview()
    preview.value = data.market_risk
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const primaryCta = computed(() => {
  if (!authStore.isLoggedIn) return { label: '무료로 시작하기', path: '/register' }
  if (authStore.needsOnboarding) return { label: '시장 전망 먼저 보기', path: '/market' }
  return { label: '내 매장 분석 보기', path: '/app' }
})

const forecast = (days) => preview.value?.forecasts?.find((item) => item.horizon_days === days)
const signed = (value) => `${value >= 0 ? '+' : ''}${Number(value).toFixed(1)}%`
</script>

<template>
  <div class="bp-landing">
    <header class="bp-public-header">
      <router-link to="/" class="landing-logo" aria-label="BOSSPROFIT 메인">
        <span>B</span><strong>BOSSPROFIT</strong>
      </router-link>
      <nav>
        <router-link v-if="!authStore.isLoggedIn" to="/login" class="bp-text-link">로그인</router-link>
        <router-link :to="primaryCta.path" class="bp-solid-link">{{ primaryCta.label }}</router-link>
      </nav>
    </header>

    <main>
      <section class="bp-hero" :style="{ '--hero-image': `url(${heroImage})` }">
        <div class="bp-hero-copy">
          <span class="bp-kicker">AI 식재료 가격 의사결정</span>
          <h1>식재료 가격이 오르기 전에,<br>영향받을 메뉴부터 알려드립니다.</h1>
          <p>시장가격 예측과 실제 매장 판매 데이터를 연결해 오늘 먼저 확인할 재료와 메뉴를 정리합니다.</p>
          <div class="bp-hero-actions">
            <router-link :to="primaryCta.path" class="bp-primary-action">{{ primaryCta.label }}</router-link>
            <router-link to="/market/rankings/tomorrow" class="bp-secondary-action">시장 전망 보기</router-link>
          </div>
          <small>로그인 전에는 어떤 매장 데이터도 표시하지 않습니다.</small>
        </div>

        <article class="bp-preview-card" aria-label="시장가격 예측 결과 미리보기">
          <div v-if="loading" class="bp-inline-state">실제 시장 전망을 불러오는 중입니다.</div>
          <div v-else-if="error || preview?.state !== 'SUCCESS'" class="bp-inline-state">
            <strong>시장 전망 준비 중</strong>
            <span>{{ preview?.message || error }}</span>
          </div>
          <template v-else>
            <header>
              <div>
                <span>실제 시장 데이터</span>
                <strong>{{ preview.item.name }} 가격 위험</strong>
              </div>
              <b>LIVE</b>
            </header>
            <div class="bp-preview-main">
              <img :src="produceImages[preview.item.image_key]" :alt="preview.item.name">
              <div>
                <span>30일 전망</span>
                <strong>{{ forecast(30) ? signed(forecast(30).change_rate) : '분석 중' }}</strong>
                <small>기준일 {{ preview.as_of_date }}</small>
              </div>
            </div>
            <dl>
              <div><dt>현재 시장가격</dt><dd>{{ formatKRW(preview.current_price) }}원 / {{ preview.item.unit }}</dd></div>
              <div><dt>7일 전망</dt><dd>{{ forecast(7) ? signed(forecast(7).change_rate) : '-' }}</dd></div>
              <div>
                <dt>30일 예측구간</dt>
                <dd v-if="forecast(30)">{{ formatKRW(forecast(30).lower_price) }}~{{ formatKRW(forecast(30).upper_price) }}원</dd>
                <dd v-else>-</dd>
              </div>
              <div><dt>신뢰도</dt><dd>{{ forecast(30)?.confidence || '검증 필요' }}</dd></div>
              <div class="wide">
                <dt>영향 예상 메뉴</dt>
                <dd>{{ preview.affected_menus?.length ? preview.affected_menus.map(item => item.name).join(', ') : '메뉴 재료 연결 필요' }}</dd>
              </div>
            </dl>
          </template>
        </article>
      </section>

      <section class="bp-feature-strip">
        <article>
          <span>01</span>
          <div><h2>시장가격 예측</h2><p>7일·30일 전망과 예측구간</p></div>
          <strong>{{ preview?.state === 'SUCCESS' ? preview.item.name : '시장 품목' }}</strong>
        </article>
        <article>
          <span>02</span>
          <div><h2>내 메뉴 원가 영향</h2><p>레시피 연결 시 메뉴별 계산</p></div>
          <strong>{{ preview?.impact_state === 'READY' ? '분석 가능' : '연결 필요' }}</strong>
        </article>
        <article>
          <span>03</span>
          <div><h2>위기 대응 전략</h2><p>선매입·관망·대체재 확인</p></div>
          <strong>근거와 한계 표시</strong>
        </article>
      </section>

      <section class="bp-market-links">
        <div>
          <span class="bp-kicker">MARKET BRIEFING</span>
          <h2>오늘 시장에서 먼저 볼 순위</h2>
          <p>실제 가격 변화와 예측 결과를 TOP 5로 확인하세요.</p>
        </div>
        <div>
          <router-link to="/market/rankings/volume"><b>01</b><span>거래량 TOP 5</span><i>→</i></router-link>
          <router-link to="/market/rankings/today"><b>02</b><span>오늘 변동 TOP 5</span><i>→</i></router-link>
          <router-link to="/market/rankings/tomorrow"><b>03</b><span>내일 예상 변동 TOP 5</span><i>→</i></router-link>
        </div>
      </section>

      <section class="bp-trust-note">
        <strong>데이터가 없으면 판단하지 않습니다.</strong>
        <p>판매성과와 수익성을 구분하고, 레시피가 없으면 메뉴 원가 영향을 계산하지 않습니다.</p>
      </section>
    </main>
  </div>
</template>
