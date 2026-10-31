<template>
  <div v-if="total > limit" class="more">
    <UiButton variant="ghost" size="sm" @click="$emit('toggle')">
      {{ open ? 'Show fewer' : `Show all ${total} ${label}` }}
    </UiButton>
  </div>
</template>

<script setup>
import UiButton from '../../components/ui/UiButton.vue'

defineProps({
  total: { type: Number, required: true },
  limit: { type: Number, required: true }, // the preview size: with no more items than this there is nothing to show
  open: { type: Boolean, default: false },
  label: { type: String, default: '' },
})
defineEmits(['toggle'])
</script>

<style scoped>
.more { margin-top: var(--space-3); }
</style>
