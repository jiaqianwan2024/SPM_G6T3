<template>
  <section class="block" :aria-labelledby="id">
    <header class="head">
      <h3 :id="id">{{ title }}</h3>
      <span v-if="count !== null" class="count">{{ count }}</span>
      <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
    </header>
    <slot />
  </section>
</template>

<script setup>
import { uid } from '../../composables/uid'

defineProps({
  title: { type: String, required: true },
  count: { type: Number, default: null },
})
const id = uid('section')
</script>

<style scoped>
.block { margin-bottom: var(--space-6); }
.head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
h3 { margin: 0; font-size: var(--fs-lg); }
.count {
  padding: 1px 9px;
  border-radius: var(--radius-pill);
  background: var(--glass-strong);
  color: var(--body);
  font-size: var(--fs-xs);
}
.actions { margin-left: auto; display: flex; gap: var(--space-2); }
</style>
