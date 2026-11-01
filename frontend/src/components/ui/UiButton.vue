<template>
  <button class="ui-btn" :class="[`is-${variant}`, `is-${size}`, { 'is-loading': loading }]"
          :type="type" :disabled="disabled || loading" :aria-busy="loading || undefined">
    <span v-if="loading" class="spinner" aria-hidden="true" />
    <slot />
  </button>
</template>

<script setup>
// variant: solid | outline | ghost | danger. size: sm | md.
defineProps({
  variant: { type: String, default: 'solid' },
  size: { type: String, default: 'md' },
  type: { type: String, default: 'button' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
</script>

<style scoped>
.ui-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-pill);
  font: 500 var(--fs-sm) var(--font);
  letter-spacing: .04em;
  cursor: pointer;
  transition: transform .4s var(--ease-out), box-shadow .4s var(--ease-out),
              background .4s var(--ease-out), color .4s var(--ease-out),
              border-color .4s var(--ease-out);
}
.ui-btn.is-md { padding: 11px 24px; }
.ui-btn.is-sm { padding: 7px 16px; font-size: var(--fs-xs); }

.ui-btn.is-solid {
  background: linear-gradient(135deg, var(--iris), #B57BFF);
  color: #0B0518;
  font-weight: 600;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, .12) inset, 0 8px 30px rgba(124, 77, 255, .35);
}
.ui-btn.is-solid:hover:not(:disabled) { transform: translateY(-2px); }

.ui-btn.is-outline {
  background: rgba(255, 255, 255, .02);
  border-color: var(--hairline);
  color: var(--text);
}
.ui-btn.is-outline:hover:not(:disabled) {
  border-color: rgba(167, 139, 250, .5);
  background: rgba(167, 139, 250, .08);
}

.ui-btn.is-ghost { background: none; color: var(--body); }
.ui-btn.is-ghost:hover:not(:disabled) { color: var(--text); }

.ui-btn.is-danger {
  background: rgba(255, 107, 138, .12);
  border-color: rgba(255, 107, 138, .4);
  color: var(--danger);
}
.ui-btn.is-danger:hover:not(:disabled) { background: rgba(255, 107, 138, .22); }

.ui-btn:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.ui-btn:disabled { opacity: .5; cursor: not-allowed; }

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (prefers-reduced-motion: reduce) {
  .ui-btn:hover { transform: none !important; }
  .spinner { animation-duration: 1.6s; }
}
</style>
