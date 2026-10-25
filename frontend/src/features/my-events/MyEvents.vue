<template>
  <div class="my-events">
    <p v-if="loading" class="empty-note">Loading your events…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <div v-else-if="!events.length" data-testid="organiser-events-empty">
      <p class="empty-note">Create your first request to get started.</p>
      <button type="button" class="btn btn-solid" data-testid="organiser-empty-create" @click="create">
        New request
      </button>
    </div>

    <template v-else>
      <div class="toolbar">
        <label class="search">
          Search
          <input v-model="query" type="search" placeholder="Event name" data-testid="organiser-event-search" />
        </label>
        <label>
          Category
          <select v-model="category" data-testid="organiser-event-category">
            <option value="">All categories</option>
            <option v-for="name in categories" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <label>
          From
          <input v-model="fromDate" type="date" data-testid="organiser-event-from" />
        </label>
        <label>
          To
          <input v-model="toDate" type="date" data-testid="organiser-event-to" />
        </label>
        <button v-if="filtersActive" type="button" class="btn btn-ghost clear" @click="clearFilters">
          Clear
        </button>
      </div>
      <p v-if="dateRangeInvalid" class="hint">The From date is after the To date.</p>

      <div class="flags">
        <button type="button" class="flag" :class="{ active: !statusFilter }" @click="statusFilter = ''">
          All <span>{{ narrowed.length }}</span>
        </button>
        <button
          v-for="flag in flags"
          :key="flag.status"
          type="button"
          class="flag"
          :class="{ active: statusFilter === flag.status, empty: flag.count === 0 }"
          @click="toggleStatus(flag.status)"
        >
          {{ eventStatusLabel(flag.status) }} <span>{{ flag.count }}</span>
        </button>
      </div>

      <p v-if="!visible.length" class="empty-note">No events match this search.</p>
      <div v-else data-testid="organiser-event-list" class="list">
        <div
          v-for="event in visible"
          :key="event.eventId"
          class="event-card"
          :data-testid="`organiser-event-${event.eventId}`"
          :data-lifecycle="lifecycle(event.status)"
          @click="open(event.eventId)"
        >
          <div class="event-top">
            <h3 class="event-name">{{ event.eventName || 'Untitled event' }}</h3>
            <span class="status-pill" :data-testid="`organiser-event-${event.eventId}-status`">
              {{ eventStatusLabel(event.status) }}
            </span>
          </div>
          <dl class="event-facts">
            <div>
              <dt>Category</dt>
              <dd>{{ event.category || '—' }}</dd>
            </div>
            <div>
              <dt>Date</dt>
              <dd :data-testid="`organiser-event-${event.eventId}-date`">{{ dateLabel(event) }}</dd>
            </div>
            <div>
              <dt>Time</dt>
              <dd :data-testid="`organiser-event-${event.eventId}-time`">{{ timeLabel(event) }}</dd>
            </div>
            <div>
              <dt>Location</dt>
              <dd :data-testid="`organiser-event-${event.eventId}-venue`">{{ event.preferredLocation || '—' }}</dd>
            </div>
          </dl>
          <p v-if="safetyNote(event)" class="safety-note" :data-testid="`organiser-event-${event.eventId}-safety`">
            {{ safetyNote(event) }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyEvents } from '../../api/eventService.js'
import { SAFETY_SUBMITTABLE_STATUSES, eventStatusLabel } from '../../config/eventStatus.js'
import { formatSgtDate, formatSgtTime, sgtDay } from '../../utils/datetime.js'

const router = useRouter()
const emit = defineEmits(['create'])

const STATUS_ORDER = [
  'draft',
  'submitted',
  'under review',
  'changes requested',
  'approved',
  'planning',
  'safety review',
  'safety approved',
  'preparing',
  'prepared',
  'reconsidering',
  'confirmed',
  'rejected',
  'cancelled',
  'completed',
]

const events = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const category = ref('')
const fromDate = ref('')
const toDate = ref('')
const statusFilter = ref('')

const categories = computed(() =>
  [...new Set(events.value.map((event) => event.category).filter(Boolean))].sort((a, b) => a.localeCompare(b)),
)
const dateRangeInvalid = computed(
  () => Boolean(fromDate.value && toDate.value && fromDate.value > toDate.value),
)
const filtersActive = computed(
  () => Boolean(query.value.trim() || category.value || fromDate.value || toDate.value || statusFilter.value),
)

const narrowed = computed(() => {
  const term = query.value.trim().toLowerCase()
  return events.value.filter((event) => {
    if (term && !(event.eventName || '').toLowerCase().includes(term)) return false
    if (category.value && event.category !== category.value) return false
    if (dateRangeInvalid.value || (!fromDate.value && !toDate.value)) return true
    const day = startDay(event.proposedStartAt)
    if (!day) return false
    if (fromDate.value && day < fromDate.value) return false
    if (toDate.value && day > toDate.value) return false
    return true
  })
})

const flags = computed(() => {
  // SPM-70 AC6: Rejected is always offered, so an organiser knows where a rejected request will be.
  const counts = new Map([['rejected', 0], ...events.value.map((event) => [event.status, 0])])
  for (const event of narrowed.value) {
    counts.set(event.status, (counts.get(event.status) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => statusRank(a.status) - statusRank(b.status) || a.status.localeCompare(b.status))
})

const visible = computed(() => {
  if (!statusFilter.value) return narrowed.value
  return narrowed.value.filter((event) => event.status === statusFilter.value)
})

function statusRank(status) {
  const index = STATUS_ORDER.indexOf(status)
  return index === -1 ? STATUS_ORDER.length : index
}

// The Singapore date, which is what the date filters hold.
function startDay(value) {
  return sgtDay(value)
}

function toggleStatus(status) {
  statusFilter.value = statusFilter.value === status ? '' : status
}

function clearFilters() {
  query.value = ''
  category.value = ''
  fromDate.value = ''
  toDate.value = ''
  statusFilter.value = ''
}

function lifecycle(status) {
  if (status === 'draft') return 'draft'
  if (status === 'submitted') return 'submitted'
  return status
}

// SPM-121 AC5: an event back in planning after its safety review says why.
// One waiting on the review already reads so from its status.
const SAFETY_NOTES = {
  changes_requested: 'Safety changes requested',
  rejected: 'Safety review rejected',
}

function safetyNote(event) {
  if (!SAFETY_SUBMITTABLE_STATUSES.includes(event.status)) return ''
  return SAFETY_NOTES[event.safetyReviewStatus] || ''
}

function datePart(value) {
  return formatSgtDate(value)
}

function timePart(value) {
  return formatSgtTime(value)
}

function sameDay(start, end) {
  return sgtDay(start) === sgtDay(end)
}

function dateLabel(event) {
  const start = event.proposedStartAt
  const end = event.proposedEndAt
  if (!start && !end) return 'No date set yet'
  if (!start || !end) return 'Date incomplete'
  if (sameDay(start, end)) return datePart(start)
  return `${datePart(start)} – ${datePart(end)}`
}

function timeLabel(event) {
  const start = event.proposedStartAt
  const end = event.proposedEndAt
  if (!start || !end) return '—'
  return `${timePart(start)} – ${timePart(end)} SGT`
}

function open(eventId) {
  router.push(`/app/events/${eventId}`)
}

function create() {
  emit('create')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getMyEvents()
    events.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load your events. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.my-events { display: flex; flex-direction: column; gap: 16px; width: 100%; }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; }
.hint { margin: 0; font-size: 13px; color: #ffc66d; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(200px, 1.6fr) minmax(150px, 1fr) minmax(140px, 180px) minmax(140px, 180px) auto;
  align-items: end;
  gap: 12px 16px;
}
.toolbar label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.toolbar input,
.toolbar select {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  color: var(--text);
  font: inherit;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  padding: 9px 12px;
  width: 100%;
  min-width: 0;
  color-scheme: dark;
}
.toolbar input:focus,
.toolbar select:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .5);
}
.toolbar select {
  appearance: none;
  padding-right: 32px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%23A78BFA' d='M1.4.6 6 5.2 10.6.6 12 2 6 8 0 2z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  cursor: pointer;
}
.clear { padding: 9px 8px; }

.flags { display: flex; flex-wrap: wrap; gap: 8px; }
.flag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--glass);
  border: 1px solid var(--hairline);
  color: var(--body);
  border-radius: 999px;
  padding: 6px 12px;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.flag span {
  min-width: 18px;
  text-align: center;
  font-size: 12px;
  color: var(--halo);
  background: rgba(124, 77, 255, .2);
  border-radius: 999px;
  padding: 1px 6px;
}
.flag.active {
  color: var(--text);
  border-color: rgba(167, 139, 250, .55);
  background: rgba(124, 77, 255, .16);
}
.flag.empty { opacity: .55; }

.list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: 14px;
}
.event-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: 18px 20px;
  cursor: pointer;
}
.event-card:hover { border-color: rgba(167, 139, 250, .35); background: var(--glass-strong); }
.event-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.event-name {
  margin: 0;
  font-family: var(--font);
  font-size: 18px;
  font-weight: 500;
  letter-spacing: -.02em;
  line-height: 1.3;
  color: var(--text);
}
.event-facts {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
}
.event-facts div { min-width: 0; }
.event-facts dt {
  margin: 0 0 2px;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.event-facts dd { margin: 0; font-size: 14px; line-height: 1.4; color: var(--body); }
.status-pill {
  flex-shrink: 0;
  font-size: 11px;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--halo);
  background: rgba(124, 77, 255, .18);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 999px;
  padding: 3px 8px;
}
.safety-note { margin: 0; font-size: 13px; color: #FFD9A8; }

@media (max-width: 980px) {
  .toolbar,
  .list,
  .event-facts { grid-template-columns: 1fr; }
}
</style>
