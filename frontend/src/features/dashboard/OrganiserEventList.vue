<template>
  <ul class="events">
    <li v-for="event in events" :key="event.eventId">
      <button type="button" class="event" :data-testid="`organiser-event-${event.eventId}`"
              @click="$emit('open', event.eventId)">
        <span class="top">
          <span class="name">{{ event.eventName || 'Untitled event' }}</span>
          <StatusPill :status="event.status" :data-testid="`organiser-event-${event.eventId}-status`" />
        </span>
        <span class="facts">
          <span>
            <span class="label">Venue</span>
            <span :data-testid="`organiser-event-${event.eventId}-venue`">{{ event.preferredLocation || '—' }}</span>
          </span>
          <span>
            <span class="label">Date</span>
            <span :data-testid="`organiser-event-${event.eventId}-date`">{{ eventDateLabel(event) }}</span>
          </span>
          <span>
            <span class="label">Time</span>
            <span :data-testid="`organiser-event-${event.eventId}-time`">{{ eventTimeLabel(event) }}</span>
          </span>
        </span>
      </button>
    </li>
  </ul>
</template>

<script setup>
import StatusPill from '../../components/ui/StatusPill.vue'
import { eventDateLabel, eventTimeLabel } from '../../utils/eventSchedule.js'

defineProps({ events: { type: Array, required: true } })
defineEmits(['open'])
</script>

<style scoped>
.events { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.event {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  text-align: left;
  font: inherit;
  color: var(--body);
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color .3s var(--ease-out), background .3s var(--ease-out);
}
.event:hover { border-color: rgba(167, 139, 250, .4); background: var(--glass-strong); }
.event:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.name { font: 500 var(--fs-lg) var(--font); color: var(--text); }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--space-3); font-size: var(--fs-sm); }
.facts > span { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.label { font-size: var(--fs-xs); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
</style>
