<template>
  <component :is="to ? 'button' : 'div'" class="stat" :class="{ 'is-link': to }" :type="to ? 'button' : undefined"
             @click="to && $emit('open')">
    <span class="eyebrow">{{ label }}</span>
    <span class="value">{{ value }}</span>
    <span v-if="hint" class="hint">{{ hint }}</span>
  </component>
</template>

<script setup>
// Pass `to` (any truthy value) to make the tile clickable; it emits `open`.
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: '–' },
  hint: { type: String, default: '' },
  to: { type: [String, Boolean], default: false },
})
defineEmits(['open'])
</script>

<style scoped>
.stat {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  text-align: left;
  font: inherit;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
}
.value { font: 500 var(--fs-xl) var(--font); color: var(--text); }
.hint { font-size: var(--fs-xs); color: var(--muted); }
.is-link { cursor: pointer; transition: border-color .35s var(--ease-out), background .35s var(--ease-out); }
.is-link:hover { border-color: rgba(167, 139, 250, .5); background: var(--glass-strong); }
.is-link:focus-visible { outline: none; box-shadow: var(--focus-ring); }
</style>
