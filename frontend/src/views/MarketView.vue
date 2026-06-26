<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/client'

const router = useRouter()

const TYPES = [
  { key: 'tomorrow', label: 'AI 가격 전망', sub: '30일 예상 변동률 기준' },
  { key: 'today',    label: '오늘 변동',    sub: '직전 거래일 대비 등락률' },
]

const panels = ref({ tomorrow: null, today: null })
const loadingCount = ref(TYPES.length)
const asOfDate = ref(null)

function formatPct(v) {
  if (v === null || v === undefined) return '--'
  return `${Number(v) > 0 ? '+' : ''}${Number(v).toFixed(1)}%`
}

const go = (type) => router.push(`/market/rankings/${type}`)

onMounted(async () => {
  await Promise.all(TYPES.map(async ({ key }) => {
    try {
      const { data } = await api.get(`/market/rankings/${key}/`, { params: { limit: 5 } })
      panels.value[key] = data
      if (!asOfDate.value && data.as_of_date) asOfDate.value = data.as_of_date
    } catch {
      panels.value[key] = { items: [], error: true }
    } finally {
      loadingCount.value--
    }
  }))
})
</script>

<template>
  <div class="mv">

    <div class="mv-header">
      <div>
        <span class="eyebrow">MARKET</span>
        <h1>시장 가격 전망</h1>
      </div>
      <span v-if="asOfDate" class="mv-date">기준일 {{ asOfDate }}</span>
    </div>

    <div class="mv-grid">
      <button
        v-for="t in TYPES"
        :key="t.key"
        class="mv-card"
        @click="go(t.key)"
      >
        <div class="mv-card-head">
          <strong>{{ t.label }}</strong>
          <span>{{ t.sub }}</span>
        </div>

        <div v-if="loadingCount > 0" class="mv-loading">
          <div class="spinner small"></div>
        </div>

        <div v-else-if="panels[t.key]?.error" class="mv-empty">데이터 없음</div>

        <ol v-else class="mv-list">
          <li
            v-for="(item, i) in (panels[t.key]?.items || []).slice(0, 5)"
            :key="item.code"
          >
            <b>{{ i + 1 }}</b>
            <span class="mv-item-name">{{ item.name }}</span>
            <span
              class="mv-item-rate"
              :class="item.change_rate > 3 ? 'rate-up' : item.change_rate < -3 ? 'rate-down' : 'rate-flat'"
            >
              {{ formatPct(item.change_rate) }}
            </span>
          </li>
        </ol>

        <div class="mv-card-foot">자세히 보기 →</div>
      </button>
    </div>

  </div>
</template>

<style scoped>
.mv { display: flex; flex-direction: column; gap: 20px; }

.mv-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
.mv-header h1 { font-size: 24px; font-weight: 700; margin-top: 4px; }
.mv-date { font-size: 12px; color: var(--ink-muted); padding-bottom: 4px; }

.mv-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
@media (max-width: 720px) { .mv-grid { grid-template-columns: 1fr; } }

.mv-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0;
  text-align: left;
  cursor: pointer;
  display: flex; flex-direction: column;
  transition: box-shadow .15s, border-color .15s;
}
.mv-card:hover { border-color: var(--coral); box-shadow: 0 2px 12px rgba(224,120,86,.12); }

.mv-card-head {
  padding: 16px 18px 12px;
  border-bottom: 1px solid var(--line);
}
.mv-card-head strong { display: block; font-size: 15px; font-weight: 700; color: var(--ink); }
.mv-card-head span   { font-size: 12px; color: var(--ink-muted); margin-top: 2px; display: block; }

.mv-loading { padding: 32px; display: flex; justify-content: center; }
.spinner.small { width: 20px; height: 20px; border-width: 2px; }
.mv-empty { padding: 32px; text-align: center; color: var(--ink-muted); font-size: 13px; }

.mv-list {
  list-style: none;
  padding: 8px 0;
  flex: 1;
}
.mv-list li {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 18px;
  border-bottom: 1px solid var(--line);
  font-size: 14px;
}
.mv-list li:last-child { border-bottom: none; }
.mv-list b { font-size: 12px; color: var(--ink-muted); width: 16px; flex-shrink: 0; }
.mv-item-name { flex: 1; font-weight: 500; color: var(--ink); }
.mv-item-rate { font-weight: 700; font-size: 14px; }
.rate-up   { color: #C44536; }
.rate-down { color: #2563EB; }
.rate-flat { color: var(--ink-muted); }

.mv-card-foot {
  padding: 10px 18px;
  font-size: 12px; font-weight: 600;
  color: var(--coral);
  border-top: 1px solid var(--line);
}
</style>
