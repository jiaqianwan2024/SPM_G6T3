<template>
  <div class="tabs" role="tablist" @keydown="onKeydown">
    <button
      v-for="t in normalised"
      :key="t.value"
      ref="btns"
      type="button"
      role="tab"
      class="tab"
      :class="{ active: t.value === modelValue }"
      :aria-selected="t.value === modelValue"
      :tabindex="t.value === modelValue ? 0 : -1"
      @click="$emit('update:modelValue', t.value)"
    >
      {{ t.label }}<span v-if="t.count != null" class="count">{{ t.count }}</span>
    </button>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

// tabs: strings, or { value, label, count? }. Pair with v-model and render the panel yourself.
const props = defineProps({
  modelValue: { type: String, default: '' },
  tabs: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const btns = ref([])
const normalised = computed(() =>
  props.tabs.map((t) => (typeof t === 'object' ? t : { value: t, label: t })))

// Arrow keys move between tabs, as for a native tablist.
function onKeydown(e) {
  if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
  const list = normalised.value
  const i = list.findIndex((t) => t.value === props.modelValue)
  const next = (i + (e.key === 'ArrowRight' ? 1 : -1) + list.length) % list.length
  emit('update:modelValue', list[next].value)
  btns.value[next]?.focus()
}
</script>

<style scoped>
.tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--hairline); overflow-x: auto; }
.tab {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 10px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  font: var(--fs-sm) var(--font);
  color: var(--body);
  cursor: pointer;
  white-space: nowrap;
  transition: color .3s var(--ease-out), border-color .3s var(--ease-out);
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--text); border-bottom-color: var(--iris-soft); }
.tab:focus-visible { outline: none; box-shadow: var(--focus-ring); border-radius: var(--radius); }
.count { padding: 0 7px; border-radius: var(--radius-pill); background: var(--glass-strong); font-size: var(--fs-xs); }
</style>
