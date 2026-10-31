<template>
  <ul class="events">
    <li v-for="event in events" :key="event.eventId">
      <button type="button" class="event-row" :data-testid="`organiser-event-${event.eventId}`"
              @click="$emit('open', event.eventId)">
        <span class="name">{{ event.eventName || 'Untitled event' }}</span>
        <span class="date" :data-testid="`organiser-event-${event.eventId}-date`">{{ eventDateLabel(event) }}</span>
        <span class="status-pill" :data-testid="`organiser-event-${event.eventId}-status`">
          {{ eventStatusLabel(event.status) }}
        </span>
      </button>
    </li>
  </ul>
</template>

<script setup>
import { eventStatusLabel } from '../../config/eventStatus.js'
import { eventDateLabel } from '../../utils/eventSchedule.js'

defineProps({ events: { type: Array, required: true } })
defineEmits(['open'])
</script>

<style scoped>
/* One line per event. The full card, with category, time and location, is under My Events. */
.events { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.event-row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: var(--space-4);
  min-height: var(--card-height, auto);
  padding: var(--space-3) var(--space-5);
  text-align: left;
  font: inherit;
  color: var(--body);
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color .3s var(--ease-out), background .3s var(--ease-out);
}
.event-row:hover { border-color: rgba(167, 139, 250, .35); background: var(--glass-strong); }
.event-row:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-md);
  font-weight: 500;
  color: var(--text);
}
.date { font-size: var(--fs-sm); color: var(--muted); white-space: nowrap; }
.status-pill {
  font-size: 11px;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--halo);
  background: rgba(124, 77, 255, .18);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 999px;
  padding: 3px 8px;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .event-row { grid-template-columns: minmax(0, 1fr) auto; }
  .date { grid-column: 1; grid-row: 2; }
  .status-pill { grid-column: 2; grid-row: 1; }
}
</style>
