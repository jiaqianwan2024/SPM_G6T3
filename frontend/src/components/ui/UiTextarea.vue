<template>
  <textarea class="ui-control" :class="{ invalid }" :id="id" :value="modelValue" :rows="rows"
            :aria-invalid="invalid || undefined" :aria-describedby="describedBy"
            @input="$emit('update:modelValue', $event.target.value)" />
</template>

<script setup>
// Control styles live in UiInput.vue.
defineProps({
  modelValue: { type: String, default: '' },
  rows: { type: Number, default: 4 },
  id: { type: String, default: undefined },
  describedBy: { type: String, default: undefined },
  invalid: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])
</script>
