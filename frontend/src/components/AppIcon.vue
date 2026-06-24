<script setup>
defineProps({
  name: {
    type: String,
    required: true,
  },
  size: {
    type: Number,
    default: 20,
  },
})

const paths = {
  home: ['M3 10.5 12 3l9 7.5', 'M5 9.5V21h14V9.5', 'M9 21v-7h6v7'],
  menu: ['M4 6h16', 'M4 12h16', 'M4 18h16'],
  chart: ['M4 19V9', 'M10 19V5', 'M16 19v-7', 'M22 19H2'],
  user: ['M20 21a8 8 0 0 0-16 0', 'M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z'],
  refresh: ['M20 11a8 8 0 1 0-2.34 5.66', 'M20 4v7h-7'],
  logout: ['M10 17l5-5-5-5', 'M15 12H3', 'M21 19V5a2 2 0 0 0-2-2h-6'],
  store: ['M3 9h18', 'M5 9V4h14v5', 'M5 9v11h14V9', 'M9 20v-6h6v6'],
  shield: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z', 'm9 12 2 2 4-4'],
  chevron: ['m9 18 6-6-6-6'],
  lock: ['M6 10h12v11H6z', 'M8 10V7a4 4 0 0 1 8 0v3'],
}
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="path in paths[name]" :key="path" :d="path" />
  </svg>
</template>
