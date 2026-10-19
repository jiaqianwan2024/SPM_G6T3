<template>
  <div class="browse">
    <div class="filters">
      <label class="search">
        Search
        <input v-model="search" type="search" placeholder="Event name" data-testid="browse-search" />
      </label>
      <label>
        Category
        <select v-model="category" data-testid="browse-filter-category">
          <option value="">All categories</option>
          <option v-for="name in categories" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <label>
        From
        <input v-model="fromDate" type="date" data-testid="browse-filter-from" />
      </label>
      <label>
        To
        <input v-model="toDate" type="date" data-testid="browse-filter-to" />
      </label>
    </div>

    <p v-if="loading" class="empty-note">Loading events…</p>
    <p v-else-if="error" class="form-error" data-testid="browse-error">{{ error }}</p>
    <p v-else-if="!visible.length" class="empty-note" data-testid="browse-empty">No events are open for registration.</p>

    <article
      v-for="event in visible"
      :key="event.eventId"
      class="event-card"
      :data-testid="`browse-event-${event.eventId}`"
      :data-full="event.full ? 'true' : 'false'"
    >
      <h3 class="event-name">{{ event.eventName }}</h3>
      <dl class="event-facts">
        <div>
          <dt>Category:</dt>
          <dd data-testid="browse-category">{{ event.category }}</dd>
        </div>
        <div>
          <dt>Date:</dt>
          <dd data-testid="browse-date">{{ datePart(event.proposedStartAt) }}</dd>
        </div>
        <div>
          <dt>Time:</dt>
          <dd>
            <span data-testid="browse-start">{{ timePart(event.proposedStartAt) }}</span>
            – <span data-testid="browse-end">{{ timePart(event.proposedEndAt) }}</span> SGT
          </dd>
        </div>
        <div>
          <dt>Location:</dt>
          <dd>{{ event.venueName }} · {{ event.venueLocation }}</dd>
        </div>
      </dl>
      <p class="places" data-testid="browse-remaining">
        {{ event.full ? 'Full' : `${event.remaining} place(s) remaining` }}
      </p>
      <div class="actions">
        <button type="button" class="btn btn-outline" @click="open(event.eventId)">View</button>
        <button
          v-if="!event.full"
          type="button"
          class="btn btn-solid"
          data-testid="event-register"
          @click="open(event.eventId)"
        >
          Register
        </button>
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getOpenEvents } from '../../api/eventService.js'
import { formatSgtDate, formatSgtTime, sgtDay } from '../../utils/datetime.js'

const router = useRouter()
const events = ref([])
const loading = ref(true)
const error = ref('')
const search = ref('')
const category = ref('')
const fromDate = ref('')
const toDate = ref('')

const categories = computed(() => [...new Set(events.value.map((event) => event.category).filter(Boolean))])

const visible = computed(() => events.value.filter((event) => {
  if (search.value && !event.eventName.toLowerCase().includes(search.value.toLowerCase())) return false
  if (category.value && event.category !== category.value) return false
  const start = sgtDay(event.proposedStartAt)
  if (fromDate.value && start && start < fromDate.value) return false
  if (toDate.value && start && start > toDate.value) return false
  return true
}))

function datePart(value) {
  return formatSgtDate(value)
}

function timePart(value) {
  return formatSgtTime(value)
}

function open(eventId) {
  router.push(`/app/browse/${eventId}`)
}

onMounted(async () => {
  try {
    const { data } = await getOpenEvents()
    events.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load events.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.browse { display: flex; flex-direction: column; gap: 14px; max-width: 860px; }
.filters {
  display: grid;
  grid-template-columns: minmax(180px, 1.6fr) minmax(150px, 1fr) 158px 158px;
  gap: 12px;
  align-items: end;
}
.filters label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}
.filters input,
.filters select {
  width: 100%;
  appearance: none;
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 12px;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  height: 42px;
  padding: 0 12px;
  color-scheme: dark;
}
.filters input::placeholder { color: var(--muted); }
.filters input:focus,
.filters select:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .55);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}
.filters select {
  padding-right: 34px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%23A78BFA' d='M1.4.6 6 5.2 10.6.6 12 2 6 8 0 2z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  cursor: pointer;
}
.filters input[type="date"] { padding-right: 8px; }
.filters input[type="date"]::-webkit-calendar-picker-indicator {
  filter: invert(0.8) sepia(0.5) saturate(4) hue-rotate(220deg);
  opacity: .85;
  cursor: pointer;
}
.filters input[type="search"]::-webkit-search-decoration,
.filters input[type="search"]::-webkit-search-cancel-button { display: none; }
@media (max-width: 800px) {
  .filters { grid-template-columns: 1fr 1fr; }
  .search { grid-column: 1 / -1; }
}
.event-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 18px 20px;
}
.event-name {
  margin: 0 0 12px;
  font-size: 22px;
  font-weight: 500;
  letter-spacing: -.02em;
}
.event-facts { margin: 0; display: flex; flex-direction: column; gap: 6px; }
.event-facts div { display: flex; gap: 8px; font-size: 14px; line-height: 1.4; }
.event-facts dt { margin: 0; min-width: 84px; color: var(--muted); }
.event-facts dd { margin: 0; color: var(--body); }
.places { margin: 12px 0 0; font-size: 14px; color: var(--text); }
.empty-note { font-size: 13px; color: var(--muted); }
.actions { display: flex; gap: 8px; margin-top: 14px; }
</style>
