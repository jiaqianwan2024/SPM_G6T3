<template>
  <div class="field" :class="{ 'has-error': error }">
    <label :for="id" class="label">
      {{ label }}<span v-if="required" class="req" aria-hidden="true"> *</span>
    </label>
    <!-- Slot receives the ids the control needs for label + hint/error wiring. -->
    <slot :id="id" :described-by="describedBy" :invalid="!!error" />
    <p v-if="error" :id="`${id}-error`" class="msg error" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="`${id}-hint`" class="msg">{{ hint }}</p>
  </div>
</template>

<script setup>
// Wraps any control (UiInput/UiSelect/UiTextarea or a native one):
//   <UiField label="Title" :error="err" v-slot="f"><UiInput v-model="t" v-bind="f" /></UiField>
import { computed } from 'vue'
import { uid } from '../../composables/uid'

const props = defineProps({
  label: { type: String, required: true },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false },
})
const id = uid('field')
const describedBy = computed(() =>
  props.error ? `${id}-error` : props.hint ? `${id}-hint` : undefined)
</script>

<style scoped>
.field { display: flex; flex-direction: column; gap: 6px; }
.label { font-size: var(--fs-sm); color: var(--text); }
.req { color: var(--danger); }
.msg { margin: 0; font-size: var(--fs-xs); color: var(--muted); }
.msg.error { color: var(--danger); }
</style>
