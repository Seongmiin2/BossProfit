<template>
  <span class="signal" :class="`signal-${signalColor}`">{{ signal }}</span>
</template>

<script setup>
defineProps({
  signal: String,
  signalColor: String,
})
</script>
