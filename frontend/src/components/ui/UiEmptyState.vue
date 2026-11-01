<template>
  <div class="empty" role="status">
    <p class="title">{{ title }}</p>
    <p v-if="hint" class="hint">{{ hint }}</p>
    <div v-if="$slots.default" class="action"><slot /></div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  hint: { type: String, default: '' },
})
</script>

<style scoped>
.empty {
  padding: var(--space-6) var(--space-5);
  text-align: center;
  border: 1px dashed var(--hairline);
  border-radius: var(--radius);
}
.title { margin: 0; color: var(--text); font-size: var(--fs-md); }
.hint { margin: var(--space-2) 0 0; color: var(--muted); font-size: var(--fs-sm); }
.action { margin-top: var(--space-4); }
</style>
