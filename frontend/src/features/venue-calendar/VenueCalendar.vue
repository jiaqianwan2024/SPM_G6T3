<template>
  <div class="venue-calendar">
    <router-link v-if="!embedded" class="back" to="/app?tab=Venue%20Calendar">All venues</router-link>

    <header class="heading">
      <div>
        <label v-if="embedded" class="venue-pick">
          Venue
          <select v-model="venueId" @change="load">
            <option v-for="item in venues" :key="item.venueId" :value="item.venueId">{{ item.name }}</option>
          </select>
        </label>
        <h1 v-else>{{ venue?.name || 'Venue' }}</h1>
        <p>Unavailable time is left out of search and approval. Bookings stay as they are. Times are UTC.</p>
      </div>
      <button v-if="canWrite" type="button" class="mark-btn" data-testid="mark-unavailable" @click="startCreate">
        Mark unavailable
      </button>
    </header>

    <p v-if="loadError" class="error">{{ loadError }}</p>

    <div v-else class="layout">
      <div class="calendar-shell">
      <FullCalendar ref="calendarRef" :options="calendarOptions">
        <template #eventContent="arg">
          <div
            v-if="arg.event.extendedProps.kind === 'unavailable'"
            class="event-body"
            :data-testid="`calendar-unavailable-${arg.event.extendedProps.id}`"
            data-kind="unavailable"
            @click.stop="selectedId = arg.event.extendedProps.id"
          >
            <strong>Unavailable</strong>
            <span class="kind">{{ arg.event.extendedProps.reason }}</span>
            <div v-if="canWrite && selectedId === arg.event.extendedProps.id" class="action-pop" @click.stop>
              <button type="button" @click="startEdit(arg.event.extendedProps.id)">Edit</button>
              <button type="button" class="danger" @click="cancelBlock(arg.event.extendedProps.id)">
                Cancel block
              </button>
            </div>
          </div>
          <div v-else class="event-body" data-kind="booking">
            <strong>{{ arg.event.title }}</strong>
            <span class="kind">{{ arg.event.extendedProps.status }}</span>
          </div>
        </template>
      </FullCalendar>
      </div>

      <form v-if="form.open" class="panel" @submit.prevent="save">
        <h2>{{ form.id ? 'Edit unavailability' : 'Mark unavailable' }}</h2>
        <label>
          Start (UTC)
          <input v-model="form.startsAt" type="datetime-local" required />
        </label>
        <label>
          End (UTC)
          <input v-model="form.endsAt" type="datetime-local" required />
        </label>
        <label>
          Reason
          <select v-model="form.reason" required>
            <option v-for="reason in reasons" :key="reason" :value="reason">{{ reason }}</option>
          </select>
        </label>
        <label>
          Note
          <textarea v-model="form.note" rows="3" maxlength="2000" placeholder="Optional"></textarea>
        </label>
        <p v-if="form.error" class="error">{{ form.error }}</p>
        <label v-if="form.needsAck" class="ack">
          <input v-model="form.acknowledge" type="checkbox" />
          I have seen these events. Save the block anyway. Their bookings stay as they are.
        </label>
        <div class="form-actions">
          <button type="submit" class="mark-btn" :disabled="form.saving || (form.needsAck && !form.acknowledge)">
            {{ form.saving ? 'Saving…' : 'Save block' }}
          </button>
          <button type="button" class="ghost-btn" @click="form.open = false">Close</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import FullCalendar from '@fullcalendar/vue3'
import themePlugin from '@fullcalendar/vue3/themes/monarch'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'
import listPlugin from '@fullcalendar/vue3/list'

import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/monarch/theme.css'
import '@fullcalendar/vue3/themes/monarch/palettes/purple.css'

import {
  cancelVenueUnavailability,
  createVenueUnavailability,
  getVenue,
  getVenueBookings,
  getVenueUnavailability,
  getVenues,
  updateVenueUnavailability
} from '../../api/venueService.js'
import { session } from '../../store/session.js'

const reasons = ['maintenance', 'renovation', 'safety issue', 'internal activity', 'other']
const route = useRoute()
const embedded = computed(() => route.name !== 'venue-calendar')
const venueId = ref(typeof route.params.id === 'string' ? route.params.id : '')
const venues = ref([])
const venue = ref(null)
const entries = ref([])
const loadError = ref('')
const selectedId = ref('')
const calendarRef = ref(null)
const canWrite = computed(() => session.role === 'venue')
const form = reactive({
  open: false,
  id: '',
  startsAt: '',
  endsAt: '',
  reason: 'maintenance',
  note: '',
  acknowledge: false,
  needsAck: false,
  error: '',
  saving: false
})

const calendarOptions = reactive({
  colorScheme: 'light',
  timeZone: 'UTC',
  plugins: [themePlugin, dayGridPlugin, timeGridPlugin, listPlugin],
  headerToolbar: {
    start: 'today prev,next title',
    end: 'dayGridMonth,timeGridWeek,listWeek'
  },
  initialView: 'dayGridMonth',
  height: 'auto',
  dayMaxEvents: false,
  eventDisplay: 'block',
  events: [],
  eventClassNames(arg) {
    return [arg.event.extendedProps.kind]
  },
  eventClick(arg) {
    if (arg.event.extendedProps.kind === 'unavailable') {
      selectedId.value = arg.event.extendedProps.id
    }
  }
})

onMounted(async () => {
  if (embedded.value) {
    try {
      const { data } = await getVenues()
      venues.value = data
      if (!venueId.value && data.length) venueId.value = data[0].venueId
    } catch {
      loadError.value = 'Could not load venues.'
      return
    }
  }
  if (venueId.value) await load()
})

async function load() {
  if (!venueId.value) return
  loadError.value = ''
  try {
    const [venueRes, blockRes, bookingRes] = await Promise.all([
      getVenue(venueId.value),
      getVenueUnavailability(venueId.value),
      getVenueBookings({ venueId: venueId.value })
    ])
    venue.value = venueRes.data
    const blocks = blockRes.data.map((block) => ({
      id: block.unavailabilityId,
      kind: 'unavailable',
      reason: block.reason,
      note: block.note,
      startsAt: block.startsAt,
      endsAt: block.endsAt,
      createdAt: block.createdAt
    }))
    const bookings = bookingRes.data
      .filter((booking) => booking.status === 'approved' || booking.status === 'pending')
      .map((booking) => ({
        id: booking.bookingId,
        kind: 'booking',
        title: booking.eventName || booking.eventId,
        status: booking.status,
        startsAt: booking.startsAt,
        endsAt: booking.endsAt,
        createdAt: booking.createdAt
      }))
    entries.value = [...blocks, ...bookings]
    calendarOptions.events = entries.value.map(toCalendarEvent)
    await nextTick()
    showNearbyMonth()
  } catch {
    loadError.value = 'Could not load this venue calendar.'
  }
}

function toCalendarEvent(entry) {
  const blocked = entry.kind === 'unavailable'
  return {
    id: `${entry.kind}-${entry.id}`,
    title: blocked ? 'Unavailable' : entry.title,
    start: ensureZ(entry.startsAt),
    end: ensureZ(entry.endsAt),
    backgroundColor: blocked ? '#9a3412' : '#5b21b6',
    borderColor: blocked ? '#9a3412' : '#5b21b6',
    textColor: '#ffffff',
    extendedProps: entry
  }
}

function showNearbyMonth() {
  const api = calendarRef.value?.getApi?.()
  if (!api) return
  const now = Date.now()
  const horizon = now + 400 * 24 * 60 * 60 * 1000
  const nearby = entries.value
    .filter((entry) => entry.kind === 'unavailable')
    .map((entry) => ({ entry, time: new Date(ensureZ(entry.startsAt)).getTime() }))
    .filter((item) => item.time >= now - 24 * 60 * 60 * 1000 && item.time <= horizon)
    .sort((a, b) => String(b.entry.createdAt).localeCompare(String(a.entry.createdAt)))
  if (nearby.length) api.gotoDate(ensureZ(nearby[0].entry.startsAt))
  else api.today()
}

function entryById(id) {
  return entries.value.find((entry) => entry.id === id)
}

function startCreate() {
  selectedId.value = ''
  Object.assign(form, {
    open: true,
    id: '',
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

function startEdit(id) {
  const entry = entryById(id)
  if (!entry) return
  selectedId.value = id
  Object.assign(form, {
    open: true,
    id,
    startsAt: toInput(entry.startsAt),
    endsAt: toInput(entry.endsAt),
    reason: entry.reason,
    note: entry.note || '',
    acknowledge: false,
    needsAck: false,
    error: '',
    saving: false
  })
}

async function save() {
  form.saving = true
  form.error = ''
  const body = {
    startsAt: toUtc(form.startsAt),
    endsAt: toUtc(form.endsAt),
    reason: form.reason,
    note: form.note,
    acknowledgeConflicts: form.acknowledge
  }
  try {
    if (form.id) await updateVenueUnavailability(venueId.value, form.id, body)
    else await createVenueUnavailability(venueId.value, body)
    form.open = false
    await load()
  } catch (err) {
    const detail = err?.response?.data?.detail
    form.error = message(detail)
    form.needsAck = err?.response?.status === 409
    if (!form.needsAck) form.acknowledge = false
  } finally {
    form.saving = false
  }
}

async function cancelBlock(id) {
  if (!window.confirm('Cancel this unavailability block? The time can be booked again.')) return
  try {
    await cancelVenueUnavailability(venueId.value, id)
    if (form.id === id) form.open = false
    selectedId.value = ''
    await load()
  } catch (err) {
    form.open = true
    form.error = message(err?.response?.data?.detail) || 'Could not cancel this block.'
  }
}

function message(detail) {
  if (!detail) return 'Could not save this block.'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || 'Check this field.').join(' ')
  return 'Could not save this block.'
}

function ensureZ(value) {
  const text = String(value)
  if (text.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(text)) return text
  return `${text}Z`
}

function toUtc(value) {
  return value.length === 16 ? `${value}:00Z` : value
}

function toInput(value) {
  const match = String(value).match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})/)
  return match ? match[1] : ''
}
</script>

<style scoped>
.venue-calendar { width: 100%; }
.back { color: #c4b5fd; text-decoration: none; font-size: 14px; }
.heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin: 12px 0 18px;
  padding-right: 72px;
}
h1 { margin: 0 0 6px; font-size: 28px; }
.heading p { margin: 0; color: var(--muted, #b7a8d4); }
.venue-pick { display: flex; flex-direction: column; gap: 6px; font-size: 14px; min-width: 260px; max-width: 420px; }
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.layout:has(.panel) { grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr); }
.event-body {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
  padding: 4px 6px;
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.25;
  white-space: normal;
}
.event-body[data-kind='unavailable'] { background: #9a3412; }
.event-body[data-kind='booking'] { background: #5b21b6; }
.kind { text-transform: capitalize; color: #fff7ed; }
.action-pop {
  position: absolute;
  z-index: 40;
  top: calc(100% + 4px);
  left: 0;
  display: flex;
  gap: 6px;
  padding: 6px;
  background: #1a1030;
  border: 1px solid #c4b5fd;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, .4);
}
.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--hairline, rgba(243, 238, 255, 0.16));
  border-radius: 12px;
  background: rgba(26, 16, 48, 0.55);
}
.panel h2 { margin: 0; font-size: 18px; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 14px; }
input, select, textarea {
  width: 100%;
  color: #f3eeff;
  background: #1a1030;
  color-scheme: dark;
  border: 1px solid rgba(243, 238, 255, 0.2);
  border-radius: 8px;
  padding: 8px 10px;
}
select option { background: #1a1030; color: #f3eeff; }
.ack { flex-direction: row; align-items: flex-start; }
.ack input { width: auto; margin-top: 3px; }
.mark-btn, .ghost-btn, .action-pop button {
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}
.mark-btn {
  flex-shrink: 0;
  color: #fff;
  background: #6d28d9;
  border: 1px solid #6d28d9;
}
.ghost-btn, .action-pop button {
  color: #f3eeff;
  background: #2a1458;
  border: 1px solid #c4b5fd;
}
.action-pop button { padding: 6px 10px; }
.action-pop .danger { color: #ffd0d0; border-color: #ffb4b4; }
.mark-btn:disabled { opacity: 0.55; cursor: default; }
.form-actions { display: flex; gap: 8px; }
.error { color: #ffb4b4; margin: 8px 0 0; white-space: pre-wrap; }
.calendar-shell {
  min-width: 0;
  background: #fff;
  color: #1c1233;
  border-radius: 16px;
  padding: 12px 16px 16px;
  overflow: auto;
}
.calendar-shell :deep(button),
.calendar-shell :deep([role='tab']) {
  color: #1c1233;
  background: #f4f0fb;
  border: 1px solid #d9d0ea;
  border-radius: 8px;
  font-weight: 650;
}
.calendar-shell :deep([aria-selected='true']) {
  color: #fff;
  background: #5b21b6;
  border-color: #5b21b6;
}
.calendar-shell :deep(a),
.calendar-shell :deep(h2) {
  color: #1c1233;
}
.action-pop button {
  color: #f3eeff;
  background: #2a1458;
  border: 1px solid #c4b5fd;
}
@media (max-width: 900px) {
  .layout, .layout:has(.panel), .heading { grid-template-columns: 1fr; }
  .heading { display: flex; flex-direction: column; }
}
</style>
