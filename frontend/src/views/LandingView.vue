<script setup>
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import heroImage from '@/assets/hero.png'

const authStore = useAuthStore()
const isLoggedIn = computed(() => authStore.isLoggedIn)

const features = [
  {
    icon: '🧮',
    title: '메뉴 원가 분석',
    desc: '재료 사용량과 단가를 기반으로 메뉴별 원가·원가율을 자동 계산합니다.',
  },
  {
    icon: '🥬',
    title: '식재료 시세 연동',
    desc: '외부 시세를 불러와 식자재 단가에 반영하고 수익성을 다시 계산합니다.',
  },
  {
    icon: '📈',
    title: '수익성 추이',
    desc: '홀·포장·배달 마진과 월 예상 이익을 시계열 차트로 추적합니다.',
  },
]

const steps = [
  { no: '01', title: '메뉴·재료 등록', desc: '판매 메뉴와 식재료, 레시피 사용량을 입력합니다.' },
  { no: '02', title: '가정 설정', desc: '판매 비중, 배달 수수료 등 매장 손익 가정을 맞춥니다.' },
  { no: '03', title: '신호등 진단', desc: '메뉴별 수익성을 신호등으로 한눈에 진단합니다.' },
]
</script>

<template>
  <div class="landing">
    <!-- HERO -->
    <section class="hero">
      <div class="hero-text">
        <span class="hero-eyebrow">소규모 외식 자영업자를 위한</span>
        <h1>
          메뉴 한 그릇의<br />
          <span class="coral">진짜 이익</span>을 계산하세요
        </h1>
        <p class="hero-desc">
          BOSSPROFIT는 재료 원가, 배달 수수료, 포장비까지 반영해
          메뉴별 마진과 월 예상 이익을 한 화면에서 보여줍니다.
        </p>
        <div class="hero-cta">
          <router-link to="/dashboard" class="btn-primary">대시보드 보기</router-link>
          <router-link v-if="!isLoggedIn" to="/register" class="btn-ghost">무료로 시작하기</router-link>
          <router-link v-else to="/market" class="btn-ghost">시세 연동하기</router-link>
        </div>
        <div class="hero-stats">
          <div><strong>21</strong><span>샘플 메뉴</span></div>
          <div><strong>35</strong><span>식재료</span></div>
          <div><strong>5</strong><span>수익성 신호</span></div>
        </div>
      </div>
      <div class="hero-visual">
        <img :src="heroImage" alt="BOSSPROFIT" />
      </div>
    </section>

    <!-- FEATURES -->
    <section class="section">
      <div class="sect-head">
        <span class="sect-label">주요 기능</span>
        <h2>원가부터 시세까지, 한 번에</h2>
      </div>
      <div class="feature-grid">
        <div v-for="f in features" :key="f.title" class="feature-card">
          <div class="feature-icon">{{ f.icon }}</div>
          <h3>{{ f.title }}</h3>
          <p>{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <!-- HOW IT WORKS -->
    <section class="section">
      <div class="sect-head">
        <span class="sect-label">사용 방법</span>
        <h2>이렇게 동작해요</h2>
      </div>
      <div class="step-grid">
        <div v-for="s in steps" :key="s.no" class="step-card">
          <div class="step-no">{{ s.no }}</div>
          <h3>{{ s.title }}</h3>
          <p>{{ s.desc }}</p>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="cta-banner">
      <div>
        <h2>지금 내 메뉴의 수익성을 진단해 보세요</h2>
        <p>로그인하면 메뉴·재료를 직접 등록하고 시세를 반영할 수 있습니다.</p>
      </div>
      <div class="cta-actions">
        <router-link to="/dashboard" class="btn-primary">대시보드 열기</router-link>
        <router-link v-if="!isLoggedIn" to="/login" class="btn-ghost light">로그인</router-link>
      </div>
    </section>
  </div>
</template>

<style scoped>
.landing { padding-bottom: 24px; }

/* HERO */
.hero {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 40px;
  align-items: center;
  background: var(--ink);
  color: var(--cream);
  border-radius: 8px;
  border-bottom: 4px solid var(--coral);
  padding: 56px 48px;
  margin-bottom: 56px;
}

.hero-eyebrow {
  display: inline-block;
  font-size: 13px;
  letter-spacing: 0.12em;
  color: var(--coral);
  margin-bottom: 16px;
}

.hero-text h1 {
  font-family: 'Noto Serif KR', serif;
  font-size: 42px;
  font-weight: 900;
  line-height: 1.25;
  letter-spacing: -0.02em;
}

.hero-text h1 .coral { color: var(--coral); }

.hero-desc {
  margin-top: 20px;
  font-size: 16px;
  color: rgba(250, 246, 239, 0.78);
  max-width: 520px;
}

.hero-cta {
  margin-top: 32px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-stats {
  margin-top: 40px;
  display: flex;
  gap: 40px;
}

.hero-stats div { display: flex; flex-direction: column; }
.hero-stats strong {
  font-family: 'Noto Serif KR', serif;
  font-size: 30px;
  font-weight: 900;
  color: var(--coral);
}
.hero-stats span { font-size: 12px; color: rgba(250, 246, 239, 0.6); }

.hero-visual { text-align: center; }
.hero-visual img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}

/* BUTTONS */
.btn-primary {
  background: var(--coral);
  color: white;
  padding: 12px 24px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 14px;
  transition: background 0.15s;
}
.btn-primary:hover { background: var(--coral-deep); color: white; }

.btn-ghost {
  border: 1px solid var(--coral);
  color: var(--coral);
  padding: 12px 24px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}
.btn-ghost:hover { background: var(--coral); color: white; }
.btn-ghost.light { border-color: rgba(250, 246, 239, 0.5); color: var(--cream); }
.btn-ghost.light:hover { background: rgba(250, 246, 239, 0.12); color: var(--cream); }

/* SECTIONS */
.section { margin-bottom: 56px; }

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.feature-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-top: 3px solid var(--coral);
  padding: 28px 24px;
}
.feature-icon { font-size: 32px; margin-bottom: 12px; }
.feature-card h3 {
  font-family: 'Noto Serif KR', serif;
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 8px;
}
.feature-card p { font-size: 14px; color: var(--ink-soft); }

.step-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.step-card {
  background: var(--cream-deep);
  border: 1px solid var(--line);
  padding: 28px 24px;
}
.step-no {
  font-family: 'Noto Serif KR', serif;
  font-size: 28px;
  font-weight: 900;
  color: var(--coral);
  margin-bottom: 8px;
}
.step-card h3 { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.step-card p { font-size: 14px; color: var(--ink-soft); }

/* CTA */
.cta-banner {
  background: var(--ink);
  color: var(--cream);
  border-left: 4px solid var(--coral);
  border-radius: 6px;
  padding: 36px 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}
.cta-banner h2 {
  font-family: 'Noto Serif KR', serif;
  font-size: 24px;
  font-weight: 900;
  margin-bottom: 6px;
}
.cta-banner p { font-size: 14px; color: rgba(250, 246, 239, 0.7); }
.cta-actions { display: flex; gap: 12px; flex-wrap: wrap; }

/* RESPONSIVE */
@media (max-width: 900px) {
  .hero {
    grid-template-columns: 1fr;
    padding: 40px 28px;
  }
  .hero-visual { order: -1; }
  .hero-text h1 { font-size: 32px; }
  .feature-grid, .step-grid { grid-template-columns: 1fr; }
}
</style>
