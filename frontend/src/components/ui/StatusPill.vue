<template>
  <span class="status-pill" :class="`tone-${tone}`">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { eventStatusLabel, eventStatusTone } from '../../config/eventStatus'

// Pass an event status; label and colour come from config/eventStatus.js.
const props = defineProps({ status: { type: String, default: '' } })
const label = computed(() => eventStatusLabel(props.status))
const tone = computed(() => eventStatusTone(props.status))
</script>

<style scoped>
.status-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  border: 1px solid currentColor;
  font-size: var(--fs-xs);
  font-weight: 500;
  letter-spacing: .04em;
  white-space: nowrap;
}
.tone-success { color: var(--success); background: rgba(56, 224, 200, .1); }
.tone-warning { color: var(--warning); background: rgba(245, 196, 81, .1); }
.tone-danger { color: var(--danger); background: rgba(255, 107, 138, .1); }
.tone-info { color: var(--info); background: rgba(167, 139, 250, .1); }
.tone-neutral { color: var(--body); background: var(--glass); }
</style>
