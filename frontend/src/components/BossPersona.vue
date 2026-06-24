<script setup>
import femaleImage from '@/assets/illustrations/persona-female.png'
import maleImage from '@/assets/illustrations/persona-male.png'

const props = defineProps({
  persona: {
    type: String,
    default: 'female',
    validator: (value) => ['female', 'male'].includes(value),
  },
  alt: {
    type: String,
    default: '',
  },
})

const images = {
  female: femaleImage,
  male: maleImage,
}
</script>

<template>
  <img
    :src="images[props.persona]"
    :alt="props.alt"
    class="boss-persona"
    loading="lazy"
  >
</template>
