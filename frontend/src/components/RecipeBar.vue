<template>
  <div class="recipe-bar">
    <div class="fill" :style="{ width: percentage + '%' }"></div>
    <div class="pct">{{ percentage.toFixed(1) }}%</div>
  </div>
</template>

<script setup>
defineProps({
  percentage: {
    type: Number,
    default: 0,
  },
})
</script>
