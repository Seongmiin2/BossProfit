<template>
  <div class="kpi">
    <div class="kpi-label">{{ label }}</div>
    <div :class="['kpi-value', colorClass]">
      {{ value }}<span class="kpi-unit">{{ unit }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: String,
  unit: String,
  colorClass: String,
})
</script>
