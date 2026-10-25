<template>
  <select class="ui-control" :class="{ invalid }" :id="id" :value="modelValue"
          :aria-invalid="invalid || undefined" :aria-describedby="describedBy"
          @change="$emit('update:modelValue', $event.target.value)">
    <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
    <option v-for="o in normalised" :key="o.value" :value="o.value">{{ o.label }}</option>
  </select>
</template>

<script setup>
import { computed } from 'vue'

// options: array of strings, or { value, label } objects. Control styles live in UiInput.vue.
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '' },
  id: { type: String, default: undefined },
  describedBy: { type: String, default: undefined },
  invalid: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])

const normalised = computed(() =>
  props.options.map((o) => (typeof o === 'object' ? o : { value: o, label: o })))
</script>
