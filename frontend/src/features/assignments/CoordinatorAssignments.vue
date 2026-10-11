<template>
  <!-- SPM-119: the Event Coordinator Lead's view of the work under their
       supervision — each Event Coordinator with the active events assigned to them. -->
  <div class="assignments" data-testid="coordinator-assignments">
    <p v-if="loading" class="empty-note">Loading assignments…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!groups.length" class="empty-note">There are no Event Coordinators yet.</p>

    <section
      v-for="group in groups"
      v-else
      :key="group.userId"
      class="coordinator"
      :data-testid="`assignments-coordinator-${group.userId}`"
    >
      <header class="coordinator-head">
        <div>
          <h2>{{ group.name }}</h2>
          <span v-if="group.email" class="email">{{ group.email }}</span>
        </div>
        <span class="count">{{ group.events.length }} active {{ group.events.length === 1 ? 'event' : 'events' }}</span>
      </header>
      <p v-if="!group.events.length" class="empty-note">No active events assigned.</p>
      <ul v-else class="events">
        <li v-for="event in group.events" :key="event.eventId">
          <!-- AC2: the Lead can open any of those events. -->
          <button
            type="button"
            class="event-row"
            :data-testid="`assignments-event-${event.eventId}`"
            @click="open(event.eventId)"
          >
            <span class="event-name">{{ event.eventName }}</span>
            <span class="meta">
              <span class="status-pill">{{ eventStatusLabel(event.status) }}</span>
              <span v-if="event.organisationName">{{ event.organisationName }}</span>
              <span>{{ formatDate(event.proposedStartAt) }}</span>
            </span>
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getCoordinatorAssignments } from '../../api/eventService.js'
import { eventStatusLabel } from '../../config/eventStatus.js'

const router = useRouter()
const groups = ref([])
const loading = ref(true)
const error = ref('')

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : 'No date set'
}

function open(eventId) {
  router.push(`/app/events/${eventId}`)
}

async function load() {
  try {
    const { data } = await getCoordinatorAssignments()
    groups.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load the assignments. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.assignments { display: flex; flex-direction: column; gap: 16px; max-width: 820px; }
.coordinator {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 18px 20px;
}
.coordinator-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.coordinator-head h2 { margin: 0; font-size: 16px; font-weight: 500; }
.email { font-size: 12px; color: var(--muted); }
.count { font-size: 12px; color: var(--muted); }
.events { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.event-row {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 6px 12px;
  flex-wrap: wrap;
  text-align: left;
  background: rgba(255, 255, 255, .02);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  padding: 10px 12px;
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
.event-row:hover, .event-row:focus-visible { border-color: rgba(167, 139, 250, .5); outline: none; }
.event-name { font-size: 14px; }
.meta { display: flex; gap: 10px; flex-wrap: wrap; font-size: 12px; color: var(--muted); }
.empty-note { font-size: 13px; color: var(--muted); margin: 0; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}
</style>
