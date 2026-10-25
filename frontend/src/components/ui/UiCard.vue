<template>
  <component :is="as" class="ui-card" :class="{ 'is-flush': flush }">
    <header v-if="$slots.header" class="head"><slot name="header" /></header>
    <slot />
  </component>
</template>

<script setup>
defineProps({
  as: { type: String, default: 'section' },
  flush: { type: Boolean, default: false }, // no inner padding, for tables/lists
})
</script>

<style scoped>
.ui-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: var(--space-5);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}
.ui-card.is-flush { padding: 0; overflow: hidden; }
.head {
  margin-bottom: var(--space-4);
  font: 500 var(--fs-lg) var(--font);
  color: var(--text);
}
</style>
