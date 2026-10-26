<template>
  <div class="skeleton-group" role="status" aria-label="Loading">
    <span v-for="n in lines" :key="n" class="skeleton" :style="{ height, width: n === lines && lines > 1 ? '60%' : '100%' }" />
  </div>
</template>

<script setup>
// Placeholder blocks while data loads. `lines` stacks several; the last one is shorter.
defineProps({
  lines: { type: Number, default: 1 },
  height: { type: String, default: '14px' },
})
</script>

<style scoped>
.skeleton-group { display: flex; flex-direction: column; gap: var(--space-2); }
.skeleton {
  display: block;
  border-radius: var(--radius);
  background: linear-gradient(90deg, var(--glass) 25%, var(--glass-strong) 50%, var(--glass) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s linear infinite;
}
@keyframes shimmer { to { background-position: -200% 0; } }

@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; }
}
</style>
