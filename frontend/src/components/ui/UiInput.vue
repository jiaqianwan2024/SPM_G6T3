<template>
  <input class="ui-control" :class="{ invalid }" :id="id" :type="type" :value="modelValue"
         :aria-invalid="invalid || undefined" :aria-describedby="describedBy"
         @input="$emit('update:modelValue', $event.target.value)" />
</template>

<script setup>
// Pass the UiField slot props through with v-bind="f" for label/error wiring.
defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  id: { type: String, default: undefined },
  describedBy: { type: String, default: undefined },
  invalid: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])
</script>

<style>
/* Unscoped on purpose: UiInput, UiSelect and UiTextarea share one control look. */
.ui-control {
  width: 100%;
  padding: 10px 14px;
  font: var(--fs-sm) var(--font);
  color: var(--text);
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  transition: border-color .3s var(--ease-out), box-shadow .3s var(--ease-out);
}
.ui-control::placeholder { color: var(--muted); }
.ui-control:hover { border-color: rgba(167, 139, 250, .35); }
.ui-control:focus-visible { outline: none; border-color: var(--iris-soft); box-shadow: var(--focus-ring); }
.ui-control.invalid { border-color: var(--danger); }
.ui-control:disabled { opacity: .5; cursor: not-allowed; }
textarea.ui-control { min-height: 96px; resize: vertical; }

/* Native arrows hug the right edge, so draw our own chevron with room around it. */
select.ui-control {
  appearance: none;
  -webkit-appearance: none;
  padding-right: 40px;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none' stroke='%23FFFFFF' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M1 1.5l5 5 5-5'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 16px center;
  background-size: 12px 8px;
}
</style>
