<template>
  <div class="upcoming-queue">
    <div class="view-toggle">
      <button
        type="button"
        class="filter-btn"
        :class="{ active: view === 'list' }"
        data-testid="queue-view-list"
        @click="view = 'list'"
      >
        Queue
      </button>
      <button
        type="button"
        class="filter-btn"
        :class="{ active: view === 'calendar' }"
        data-testid="queue-view-calendar"
        @click="view = 'calendar'"
      >
        Calendar
      </button>
    </div>

    <EventCalendar v-if="view === 'calendar'" />

    <template v-else>
      <div class="queue-toolbar">
        <label>
          Equipment status
          <select v-model="state" data-testid="queue-filter-status" @change="load">
            <option value="">All</option>
            <option v-for="(label, value) in STATE_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <label>
          From
          <input v-model="dateFrom" type="date" data-testid="queue-filter-from" @change="load" />
        </label>
        <label>
          To
          <input v-model="dateTo" type="date" data-testid="queue-filter-to" @change="load" />
        </label>
      </div>

      <p v-if="loading" class="empty-note">Loading upcoming events…</p>
      <p v-else-if="error" class="empty-note error" data-testid="equipment-queue-error">{{ error }}</p>
      <p v-else-if="!rows.length" class="empty-note" data-testid="equipment-queue-empty">
        No upcoming events with equipment requirements match these filters. Completed and cancelled events are not shown.
      </p>

      <ul v-else class="queue-list">
        <li
          v-for="row in rows"
          :key="row.eventId"
          class="queue-row"
          :class="{ attention: row.needsAttention }"
          role="button"
          tabindex="0"
          :data-testid="`equipment-queue-${row.eventId}`"
          :data-equipment-state="row.equipmentState"
          @click="open(row)"
          @keydown.enter="open(row)"
        >
          <div class="row-head">
            <strong>{{ row.eventName }}</strong>
            <span class="pill" data-testid="queue-status">{{ row.status }}</span>
            <span class="pill state">{{ STATE_LABELS[row.equipmentState] }}</span>
            <span v-if="row.needsReverification" class="pill warn">Needs re-verification</span>
            <span v-else-if="row.needsAttention" class="pill warn">Needs attention</span>
          </div>
          <dl class="row-facts">
            <div><dt>Date</dt><dd data-testid="queue-date">{{ formatSgtDate(row.proposedStartAt) || '—' }}</dd></div>
            <div><dt>Start</dt><dd data-testid="queue-start">{{ formatSgtTime(row.proposedStartAt) || '—' }}</dd></div>
            <div><dt>End</dt><dd data-testid="queue-end">{{ formatSgtTime(row.proposedEndAt) || '—' }}</dd></div>
            <div><dt>Venue</dt><dd data-testid="queue-venue">{{ row.venueName || 'No venue booked' }}</dd></div>
            <div><dt>Coordinator</dt><dd data-testid="queue-coordinator">{{ coordinatorName(row.coordinatorId) }}</dd></div>
            <div class="wide"><dt>Equipment</dt><dd data-testid="queue-equipment-summary">{{ row.equipmentSummary }}</dd></div>
          </dl>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import EventCalendar from '../event-calendar/EventCalendar.vue'
import { getUpcomingEquipmentQueue } from '../../api/equipmentService.js'
import { getUsers } from '../../api/userService.js'
import { formatSgtDate, formatSgtTime } from '../../utils/datetime.js'

// SPM-4 AC3: where an event's equipment requests stand.
const STATE_LABELS = {
  awaiting_review: 'Awaiting review',
  partly_reserved: 'Partly reserved',
  fully_reserved: 'Fully reserved',
  unavailable: 'Unavailable',
}

const router = useRouter()
const view = ref('list')
const rows = ref([])
const loading = ref(true)
const error = ref('')
const state = ref('')
const dateFrom = ref('')
const dateTo = ref('')
// userId -> name. Display only; the queue falls back to the id.
const names = ref({})

function coordinatorName(userId) {
  if (!userId) return 'Unassigned'
  return names.value[userId] || userId
}

function open(row) {
  router.push(`/app/events/${row.eventId}/equipment`)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getUpcomingEquipmentQueue({
      state: state.value || undefined,
      dateFrom: dateFrom.value || undefined,
      dateTo: dateTo.value || undefined,
    })
    rows.value = data
  } catch {
    rows.value = []
    error.value = 'Unable to load upcoming events. Please try again.'
  } finally {
    loading.value = false
  }
}

async function loadNames() {
  try {
    const { data } = await getUsers()
    names.value = Object.fromEntries(data.map((user) => [user.userId, user.userName || user.userId]))
  } catch {
    // Non-fatal - the queue shows coordinator ids instead.
  }
}

onMounted(() => {
  load()
  loadNames()
})
</script>

<style scoped>
.upcoming-queue { display: flex; flex-direction: column; gap: 14px; }
.view-toggle { display: flex; gap: 8px; }
.queue-toolbar { display: flex; flex-wrap: wrap; gap: 14px; }
.queue-toolbar label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.queue-toolbar select,
.queue-toolbar input {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  padding: 9px 12px;
  color-scheme: dark;
}
.filter-btn {
  background: var(--glass);
  border: 1px solid var(--hairline);
  color: var(--muted);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12px;
  cursor: pointer;
}
.filter-btn.active {
  color: var(--text);
  border-color: rgba(167, 139, 250, .6);
  background: rgba(124, 77, 255, .18);
}
.empty-note { font-size: 14px; color: var(--muted); }
.empty-note.error { color: #ffb4a8; }
.queue-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.queue-row {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 16px;
  padding: 16px 20px;
  cursor: pointer;
}
.queue-row:hover,
.queue-row:focus-visible { border-color: rgba(167, 139, 250, .4); outline: none; }
.queue-row.attention { border-color: rgba(255, 180, 168, .45); }
.row-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.pill {
  font-size: 11px;
  letter-spacing: .04em;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 2px 10px;
  color: var(--muted);
  text-transform: capitalize;
}
.pill.warn { color: #ffb4a8; border-color: rgba(255, 180, 168, .45); }
.row-facts {
  margin: 12px 0 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px 16px;
}
.row-facts .wide { grid-column: 1 / -1; }
dt { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
dd { margin: 2px 0 0; font-size: 14px; }
</style>
