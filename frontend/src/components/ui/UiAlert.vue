<template>
  <div class="alert" :class="`tone-${tone}`" :role="tone === 'danger' ? 'alert' : 'status'">
    <div class="text"><slot /></div>
    <button v-if="dismissible" type="button" class="x" aria-label="Dismiss" @click="$emit('dismiss')">×</button>
  </div>
</template>

<script setup>
// tone: info | success | warning | danger. Set `dismissible` and handle `dismiss` to hide it.
defineProps({
  tone: { type: String, default: 'info' },
  dismissible: { type: Boolean, default: false },
})
defineEmits(['dismiss'])
</script>

<style scoped>
.alert {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid currentColor;
  border-radius: var(--radius);
  font-size: var(--fs-sm);
}
.text { color: var(--text); }
.tone-info { color: var(--info); background: rgba(167, 139, 250, .08); }
.tone-success { color: var(--success); background: rgba(56, 224, 200, .08); }
.tone-warning { color: var(--warning); background: rgba(245, 196, 81, .08); }
.tone-danger { color: var(--danger); background: rgba(255, 107, 138, .08); }
.x { background: none; border: none; color: var(--body); font-size: 20px; line-height: 1; cursor: pointer; border-radius: var(--radius-sm); }
.x:hover { color: var(--text); }
.x:focus-visible { outline: none; box-shadow: var(--focus-ring); }
</style>
