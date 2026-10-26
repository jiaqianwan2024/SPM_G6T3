<template>
  <div class="unavailability">
    <p v-if="loading" class="empty-note">Loading unavailability…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <template v-else>
      <div class="toolbar">
        <label class="search">
          Search
          <input
            v-model="query"
            type="search"
            placeholder="Venue, reason, note, or event"
            data-testid="unavailability-search"
          />
        </label>

        <div class="filters">
          <label>
            Venue
            <select v-model="venueId" data-testid="unavailability-venue">
              <option value="">All venues</option>
              <option v-for="venue in venues" :key="venue.venueId" :value="venue.venueId">
                {{ venue.name }}
              </option>
            </select>
          </label>
          <label>
            Reason
            <select v-model="reason" data-testid="unavailability-reason">
              <option value="">All reasons</option>
              <option v-for="item in reasons" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
          <label>
            From (SGT)
            <input v-model="fromDate" type="date" data-testid="unavailability-from" />
          </label>
          <label>
            To (SGT)
            <input v-model="toDate" type="date" data-testid="unavailability-to" />
          </label>
        </div>

        <div class="pills">
          <button
            v-for="item in whenOptions"
            :key="item.id"
            type="button"
            class="filter-btn"
            :class="{ active: when === item.id }"
            @click="when = item.id"
          >
            {{ item.label }}
          </button>
          <button type="button" class="mark-btn" data-testid="unavailability-mark" @click="openForm">
            Mark unavailable
          </button>
        </div>
      </div>

      <Teleport to="body">
        <div v-if="form.open" class="modal-backdrop" @click.self="form.open = false">
          <form class="modal mark-form" role="dialog" aria-modal="true" data-testid="unavailability-form" @submit.prevent="save">
            <h3>Mark unavailable</h3>
            <label>
              Venue
              <select v-model="form.venueId" required data-testid="unavailability-form-venue">
                <option v-for="venue in activeVenues" :key="venue.venueId" :value="venue.venueId">
                  {{ venue.name }}
                </option>
              </select>
            </label>
            <div class="form-times">
              <label>
                Start (SGT)
                <input v-model="form.startsAt" type="datetime-local" required />
              </label>
              <label>
                End (SGT)
                <input v-model="form.endsAt" type="datetime-local" required />
              </label>
            </div>
            <label>
              Reason
              <select v-model="form.reason" required>
                <option v-for="item in reasons" :key="item" :value="item">{{ item }}</option>
              </select>
            </label>
            <label>
              Note
              <textarea v-model="form.note" rows="3" maxlength="2000" placeholder="Optional"></textarea>
            </label>
            <p v-if="form.error" class="form-error">{{ form.error }}</p>
            <label v-if="form.needsAck" class="ack">
              <input v-model="form.acknowledge" type="checkbox" />
              I have seen these events. Save the block anyway. Their bookings stay as they are.
            </label>
            <div class="form-actions">
              <button type="submit" class="mark-btn" :disabled="form.saving || (form.needsAck && !form.acknowledge)">
                {{ form.saving ? 'Saving…' : 'Save block' }}
              </button>
              <button type="button" class="filter-btn" @click="form.open = false">Close</button>
            </div>
          </form>
        </div>
      </Teleport>

      <p v-if="warning" class="warning">{{ warning }}</p>
      <p class="count" data-testid="unavailability-count">
        {{ visible.length }} of {{ currentRows.length }} {{ currentRows.length === 1 ? 'block' : 'blocks' }}
      </p>

      <p v-if="!currentRows.length" class="empty-note">No current or upcoming unavailability.</p>
      <p v-else-if="!visible.length" class="empty-note" data-testid="unavailability-empty">
        Nothing matches this search. Clear a filter to see more blocks.
      </p>

      <div v-else class="list" data-testid="unavailability-list">
        <article
          v-for="row in visible"
          :key="row.unavailabilityId"
          class="card"
          :data-testid="`unavailability-${row.unavailabilityId}`"
        >
          <header>
            <strong>{{ row.venueName }}</strong>
            <span class="reason">{{ row.reason }}</span>
          </header>
          <p class="when">{{ formatWhen(row.startsAt) }} – {{ formatWhen(row.endsAt) }}</p>
          <p v-if="row.note" class="note">{{ row.note }}</p>
          <div class="events">
            <span class="events-label">Bookings in this period</span>
            <ul v-if="row.events.length">
              <li v-for="event in row.events" :key="event.bookingId">
                <span>{{ event.title }}</span>
                <span class="status" :data-status="event.status">{{ event.status }}</span>
              </li>
            </ul>
            <p v-else class="none">No pending or approved booking overlaps this block.</p>
          </div>
          <button type="button" class="open-link" @click="openOnCalendar(row)">
            Open on calendar
          </button>
        </article>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createVenueUnavailability, getVenueBookings, getVenueUnavailability, getVenues } from '../../api/venueService.js'
import { formatSgt, fromSgtInput, sgtDayEnd, sgtDayStart } from '../../utils/datetime.js'

const router = useRouter()
const reasons = ['maintenance', 'renovation', 'safety issue', 'internal activity', 'other']
const whenOptions = [
  { id: 'all', label: 'All' },
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'happening', label: 'Happening now' }
]

const loading = ref(true)
const error = ref('')
const warning = ref('')
const venues = ref([])
const rows = ref([])
const query = ref('')
const venueId = ref('')
const reason = ref('')
const fromDate = ref('')
const toDate = ref('')
const when = ref('all')
const form = reactive({
  open: false,
  venueId: '',
  startsAt: '',
  endsAt: '',
  reason: 'maintenance',
  note: '',
  acknowledge: false,
  needsAck: false,
  error: '',
  saving: false
})

const activeVenues = computed(() => venues.value.filter((venue) => venue.isActive !== false))
const currentRows = computed(() => {
  const now = Date.now()
  return rows.value.filter((row) => new Date(ensureZ(row.endsAt)).getTime() > now)
})

const visible = computed(() => {
  const needle = query.value.trim().toLowerCase()
  // The filter dates are Singapore dates.
  const from = sgtDayStart(fromDate.value)
  const to = sgtDayEnd(toDate.value)
  const now = Date.now()
  const matched = currentRows.value.filter((row) => {
    if (venueId.value && row.venueId !== venueId.value) return false
    if (reason.value && row.reason !== reason.value) return false
    if (when.value !== 'all' && timing(row, now) !== when.value) return false
    const start = new Date(ensureZ(row.startsAt)).getTime()
    const end = new Date(ensureZ(row.endsAt)).getTime()
    if (from !== null && end <= from) return false
    if (to !== null && start >= to) return false
    if (!needle) return true
    const haystack = [
      row.venueName,
      row.reason,
      row.note,
      ...row.events.flatMap((event) => [event.title, event.eventId, event.status])
    ].join(' ').toLowerCase()
    return haystack.includes(needle)
  })
  matched.sort((a, b) => new Date(ensureZ(a.startsAt)).getTime() - new Date(ensureZ(b.startsAt)).getTime())
  return matched
})

onMounted(load)

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  warning.value = ''
  try {
    const { data } = await getVenues(true)
    venues.value = data
    const settled = await Promise.allSettled(data.map(loadVenue))
    const failed = settled.filter((item) => item.status === 'rejected').length
    rows.value = settled
      .filter((item) => item.status === 'fulfilled')
      .flatMap((item) => item.value)
    if (!rows.value.length && failed) error.value = 'Could not load unavailability.'
    else if (failed) warning.value = `Could not load unavailability for ${failed} ${failed === 1 ? 'venue' : 'venues'}.`
  } catch {
    error.value = 'Could not load unavailability.'
  } finally {
    loading.value = false
  }
}

async function loadVenue(venue) {
  const [blockRes, bookingRes] = await Promise.all([
    getVenueUnavailability(venue.venueId),
    getVenueBookings({ venueId: venue.venueId })
  ])
  const bookings = bookingRes.data.filter((booking) => booking.status === 'pending' || booking.status === 'approved')
  return blockRes.data.map((block) => ({
    ...block,
    venueName: venue.name,
    events: bookings
      .filter((booking) => overlaps(block, booking))
      .map((booking) => ({
        bookingId: booking.bookingId,
        eventId: booking.eventId,
        title: booking.eventSnapshot?.eventName || booking.eventId,
        status: booking.status
      }))
  }))
}

function overlaps(block, booking) {
  const start = new Date(ensureZ(booking.setupStartsAt || booking.startsAt)).getTime()
  const end = new Date(ensureZ(booking.teardownEndsAt || booking.endsAt)).getTime()
  const blockStart = new Date(ensureZ(block.startsAt)).getTime()
  const blockEnd = new Date(ensureZ(block.endsAt)).getTime()
  return start < blockEnd && end > blockStart
}

function openOnCalendar(row) {
  const at = ensureZ(row.startsAt)
  const query = { tab: 'Venue Calendar', venue: row.venueId, at }
  router.push({ name: 'dashboard', query }).catch(() => {
    router.replace({ name: 'dashboard', query })
  })
}

function openForm() {
  Object.assign(form, {
    open: true,
    venueId: venueId.value || activeVenues.value[0]?.venueId || '',
    startsAt: '',
    endsAt: '',
    reason: 'maintenance',
    note: '',
    acknowledge: false,
    needsAck: false,
    error: '',
    saving: false
  })
}

async function save() {
  form.saving = true
  form.error = ''
  try {
    await createVenueUnavailability(form.venueId, {
      startsAt: toUtc(form.startsAt),
      endsAt: toUtc(form.endsAt),
      reason: form.reason,
      note: form.note,
      acknowledgeConflicts: form.acknowledge
    })
    form.open = false
    await load(true)
  } catch (err) {
    form.error = message(err?.response?.data?.detail)
    form.needsAck = err?.response?.status === 409
    if (!form.needsAck) form.acknowledge = false
  } finally {
    form.saving = false
  }
}

function message(detail) {
  if (!detail) return 'Could not save this block.'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || 'Check this field.').join(' ')
  return 'Could not save this block.'
}

// Typed in Singapore time, sent in UTC.
function toUtc(value) {
  return fromSgtInput(value)
}

function timing(row, now) {
  const start = new Date(ensureZ(row.startsAt)).getTime()
  const end = new Date(ensureZ(row.endsAt)).getTime()
  if (end <= now) return 'past'
  if (start > now) return 'upcoming'
  return 'happening'
}

function ensureZ(value) {
  const text = String(value)
  if (text.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(text)) return text
  return `${text}Z`
}

function formatWhen(value) {
  return formatSgt(value) || String(value)
}
</script>

<style scoped>
.unavailability { display: flex; flex-direction: column; gap: 14px; }
.toolbar { display: flex; flex-direction: column; gap: 14px; }
.search, .filters label, .mark-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.search input, .filters select, .filters input,
.mark-form input, .mark-form select, .mark-form textarea {
  width: 100%;
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  color: var(--text);
  font: inherit;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  padding: 9px 12px;
  color-scheme: dark;
}
.search input:focus, .filters select:focus, .filters input:focus,
.mark-form input:focus, .mark-form select:focus, .mark-form textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .5);
}
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.pills { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
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
.mark-btn {
  margin-left: auto;
  color: #fff;
  background: #6d28d9;
  border: 1px solid #6d28d9;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}
.mark-btn:disabled { opacity: 0.55; cursor: default; }
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(5, 2, 14, .72);
}
.modal {
  width: min(480px, 100%);
  max-height: min(640px, calc(100vh - 48px));
  overflow: auto;
}
.mark-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 22px;
  background: #140828;
  border: 1px solid rgba(167, 139, 250, .35);
  border-radius: var(--radius);
  box-shadow: 0 24px 70px rgba(4, 1, 12, .75);
}
.mark-form h3 { margin: 0; color: var(--text); font-size: 16px; }
.form-times { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-actions { display: flex; gap: 8px; }
.form-actions .mark-btn { margin-left: 0; }
.ack {
  flex-direction: row;
  align-items: flex-start;
  gap: 8px;
  text-transform: none;
  letter-spacing: 0;
  font-size: 14px;
  color: var(--body);
}
.ack input { width: auto; margin-top: 2px; }
.count, .empty-note, .warning { margin: 0; font-size: 14px; color: var(--muted); }
.warning { color: #ffb4b4; }
.form-error { color: #ffb4b4; margin: 0; }
.list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 20px;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
}
.card header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.card header strong { color: var(--text); font-size: 16px; }
.reason {
  flex-shrink: 0;
  padding: 3px 8px;
  border-radius: 999px;
  background: #b91c1c;
  color: #fff;
  font-size: 12px;
  font-weight: 650;
  text-transform: capitalize;
}
.when, .note, .none { margin: 0; font-size: 13px; color: var(--body); }
.note { color: var(--muted); }
.events { display: flex; flex-direction: column; gap: 6px; }
.events-label {
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.events ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.events li { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 14px; }
.status {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 999px;
  background: #5b21b6;
  color: #fff;
  font-size: 11px;
  text-transform: capitalize;
}
.status[data-status='approved'] { background: #15803d; }
.open-link {
  align-self: flex-start;
  margin-top: 4px;
  padding: 0;
  border: 0;
  background: none;
  color: #c4b5fd;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}
.open-link:hover { color: #f3eeff; }
@media (max-width: 900px) {
  .filters, .list, .form-times { grid-template-columns: 1fr; }
  .mark-btn { margin-left: 0; }
}
</style>
