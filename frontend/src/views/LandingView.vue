<script setup>
import { useAuthStore } from '@/stores/auth'
import heroImage from '@/assets/illustrations/bossprofit-hero.png'
import BossPersona from '@/components/BossPersona.vue'

const authStore = useAuthStore()
</script>

<template>
  <div class="public-landing">
    <header class="landing-header">
      <router-link to="/" class="landing-logo" aria-label="BOSSPROFIT 메인">
        <span>B</span>
        <strong>BOSSPROFIT</strong>
      </router-link>
      <nav>
        <router-link v-if="!authStore.isLoggedIn" to="/login" class="landing-login">로그인</router-link>
        <router-link
          :to="authStore.isLoggedIn ? (authStore.needsOnboarding ? '/onboarding' : '/app') : '/register'"
          class="landing-start"
        >
          {{ authStore.isLoggedIn ? '내 매장으로' : '무료로 시작하기' }}
        </router-link>
      </nav>
    </header>

    <main class="landing-main">
      <section
        class="landing-hero landing-photo-hero"
        :style="{ '--hero-image': `url(${heroImage})` }"
      >
        <div class="landing-copy">
          <span class="landing-kicker">식재료 가격 대응 플랫폼</span>
          <h1>
            <span>오르기 전에,</span>
            <span>움직이세요.</span>
          </h1>
          <p>
            시장 가격을 미리 보고, 내 메뉴의 손익을 계산하고,
            지금 할 일을 결정합니다.
          </p>
          <div class="landing-keywords" aria-label="핵심 서비스">
            <span>시장 가격 예측</span>
            <i></i>
            <span>내 가게 영향 계산</span>
            <i></i>
            <span>행동 전략 제안</span>
          </div>
          <div class="landing-actions">
            <router-link
              :to="authStore.isLoggedIn ? (authStore.needsOnboarding ? '/onboarding' : '/app') : '/register'"
              class="landing-primary"
            >
              {{ authStore.isLoggedIn ? '내 매장 계속하기' : '내 매장 시작하기' }}
            </router-link>
            <router-link v-if="!authStore.isLoggedIn" to="/login" class="landing-secondary">
              이미 계정이 있어요
            </router-link>
          </div>
          <small>로그인 전에는 어떤 매장 데이터도 표시하지 않습니다.</small>
        </div>
      </section>

      <section class="landing-problems">
        <article>
          <span>PRICE FORECAST</span>
          <h2>시장 가격을<br>먼저 예측합니다.</h2>
          <p>실제 가격과 1·7·30일 전망, 예측구간과 기상·수급 근거를 함께 확인합니다.</p>
        </article>
        <article>
          <span>STORE IMPACT</span>
          <h2>가격 변화가 내 메뉴에<br>미칠 영향을 계산합니다.</h2>
          <p>재료 사용량과 판매량을 연결해 메뉴 원가와 예상 이익 변화를 보여줍니다.</p>
        </article>
        <article>
          <span>BUSINESS 119</span>
          <h2>상황에 맞는 다음 행동을<br>함께 정합니다.</h2>
          <p>시장 근거와 매장 데이터를 바탕으로 구매·레시피·구성·가격 대안을 비교합니다.</p>
        </article>
      </section>

      <section class="landing-market-board">
        <div class="market-board-persona-scene" aria-label="함께 시장을 확인하는 남녀 사장님 페르소나">
          <span class="persona-scene-orbit"></span>
          <BossPersona persona="female" alt="" class="market-board-persona female" />
          <BossPersona persona="male" alt="" class="market-board-persona male" />
          <p><strong>사장님의 시장팀</strong><span>예측부터 대응까지 함께</span></p>
        </div>
        <div class="landing-board-head">
          <span class="landing-kicker">MARKET BRIEFING</span>
          <h2>오늘 시장에서<br>먼저 볼 세 가지</h2>
          <p>검색하기 전에 중요한 움직임부터 보여줍니다.</p>
        </div>
        <div class="landing-board-grid">
          <article>
            <span>01</span>
            <div>
              <small>거래량 TOP 3</small>
              <strong>가장 많이 움직인 품목</strong>
              <p>최신 완료 거래일의 도매시장 거래량·반입량 기준</p>
            </div>
          </article>
          <article>
            <span>02</span>
            <div>
              <small>오늘 변동 TOP 3</small>
              <strong>전일보다 크게 오른·내린 품목</strong>
              <p>전 거래일 대비 절대 등락률 기준</p>
            </div>
          </article>
          <article class="forecast">
            <span>03</span>
            <div>
              <small>내일 예상 변동 TOP 3</small>
              <strong>내일 움직임이 클 것으로 보이는 품목</strong>
              <p>예측값과 신뢰도를 함께 표시</p>
            </div>
          </article>
        </div>
      </section>

      <section class="landing-data-principle">
        <div>
          <span class="landing-kicker">데이터 원칙</span>
          <h2>사장님의 데이터는 로그인 후,<br>해당 매장에서만 보입니다.</h2>
        </div>
        <ul>
          <li>사용자별 매장 데이터 분리</li>
          <li>예측값과 신뢰구간 동시 제공</li>
          <li>AI 답변에 기준일과 근거 표시</li>
        </ul>
      </section>
    </main>
  </div>
</template>
