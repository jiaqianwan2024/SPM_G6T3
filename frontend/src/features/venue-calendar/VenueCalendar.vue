<template>
  <div class="venue-calendar">
    <router-link v-if="!embedded" class="back" to="/app?tab=Venue%20Calendar">All venues</router-link>

    <header class="heading">
      <label v-if="embedded" class="venue-pick">
        Venue
        <select v-model="venueId" @change="changeVenue">
          <option v-for="item in venues" :key="item.venueId" :value="item.venueId">{{ item.name }}</option>
        </select>
      </label>
      <h1 v-else>{{ venue?.name || 'Venue' }}</h1>
    </header>

    <p v-if="loadError" class="error">{{ loadError }}</p>

    <div v-else class="layout">
      <div class="calendar-column">
        <div class="calendar-shell">
          <p v-if="needsRecheck" class="reverify-banner" data-testid="calendar-reverify">
            A booking on this calendar needs re-verification.
          </p>
          <div class="calendar-bar">
            <ul class="legend">
              <li><span class="swatch pending"></span>Pending <span class="count">{{ counts.pending }}</span></li>
              <li><span class="swatch approved"></span>Approved <span class="count">{{ counts.approved }}</span></li>
              <li><span class="swatch unavailable"></span>Unavailable <span class="count">{{ counts.unavailable }}</span></li>
            </ul>
            <button v-if="canWrite" type="button" class="mark-btn" data-testid="mark-unavailable" @click="startCreate">
              Mark unavailable
            </button>
          </div>
          <FullCalendar ref="calendarRef" :options="calendarOptions">
        <template #eventContent="arg">
          <div
            v-if="arg.event.extendedProps.kind === 'unavailable'"
            class="event-body"
            :data-testid="`calendar-unavailable-${arg.event.extendedProps.id}`"
            data-kind="unavailable"
            @mouseenter="openDetail($event, arg.event.extendedProps, false)"
            @mouseleave="scheduleClose"
            @click.stop="selectBlock(arg.event.extendedProps.id, $event)"
          >
            <strong>Unavailable</strong>
            <span class="kind">{{ arg.event.extendedProps.reason }}</span>
          </div>
          <div
            v-else-if="arg.event.extendedProps.kind === 'draft'"
            class="event-body"
            data-kind="draft"
          >
            <strong>Selected</strong>
          </div>
          <div
            v-else
            class="event-body"
            data-kind="booking"
            :data-status="arg.event.extendedProps.status"
            @mouseenter="openDetail($event, arg.event.extendedProps, false)"
            @mouseleave="scheduleClose"
            @click.stop="openDetail($event, arg.event.extendedProps, true)"
          >
            <strong>{{ arg.event.title }}</strong>
            <span class="kind">{{ arg.event.extendedProps.status }}</span>
          </div>
        </template>
      </FullCalendar>
        </div>
      </div>

      <form v-if="form.open" class="panel" @submit.prevent="save">
        <h2>{{ form.id ? 'Edit unavailability' : 'Mark unavailable' }}</h2>
        <p v-if="form.id" class="hint">Update the time, reason, or note. The block stays where it is until you save. Times are Singapore time (SGT).</p>
        <p v-else class="hint">Click a day, or drag across one or more days or times. The selected range stays on the calendar until you close this form or choose a different range. Times are Singapore time (SGT).</p>
        <label>
          Start (SGT)
          <input v-model="form.startsAt" type="datetime-local" required />
        </label>
        <label>
          End (SGT)
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
          <button type="button" class="ghost-btn" @click="closeForm">Close</button>
        </div>
      </form>
    </div>

    <Teleport to="body">
      <aside
        v-if="detail.entry"
        class="detail-card"
        :style="{ top: `${detail.top}px`, left: `${detail.left}px` }"
        @mouseenter="holdDetail"
        @mouseleave="releaseDetail"
      >
        <header>
          <strong>{{ detail.entry.kind === 'unavailable' ? 'Unavailable' : detail.entry.title }}</strong>
          <button type="button" @click="closeDetail">Close</button>
        </header>
        <dl>
          <div v-for="row in detailRows" :key="row.label">
            <dt>{{ row.label }}</dt>
            <dd>{{ row.value }}</dd>
          </div>
        </dl>
        <div v-if="canWrite && detail.entry.kind === 'unavailable'" class="detail-actions">
          <button type="button" @click="startEdit(detail.entry.id)">Edit</button>
          <button type="button" class="danger" @click="cancelBlock(detail.entry.id)">Cancel block</button>
        </div>
      </aside>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import FullCalendar from '@fullcalendar/vue3'
import themePlugin from '@fullcalendar/vue3/themes/monarch'
import interactionPlugin from '@fullcalendar/vue3/interaction'
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
import { SGT_ZONE, formatSgt, fromSgtInput, sgtDay, toSgtInput } from '../../utils/datetime.js'

const props = defineProps({
  focusVenue: { type: String, default: '' },
  focusAt: { type: String, default: '' }
})
const reasons = ['maintenance', 'renovation', 'safety issue', 'internal activity', 'other']
const route = useRoute()
const embedded = computed(() => route.name !== 'venue-calendar')
const venueId = ref(props.focusVenue || (typeof route.params.id === 'string' ? route.params.id : ''))
const venues = ref([])
const venue = ref(null)
const entries = ref([])
const needsRecheck = computed(() => entries.value.some((entry) => entry.reverificationNote))
const visibleRange = ref(null)
const loadError = ref('')
const calendarRef = ref(null)
const detail = reactive({ entry: null, pinned: false, overCard: false, top: 0, left: 0 })
let hideTimer = 0
const canWrite = computed(() => session.role === 'venue')
const counts = computed(() => {
  const tally = { pending: 0, approved: 0, unavailable: 0 }
  const range = visibleRange.value
  for (const entry of entries.value) {
    if (range && !overlapsRange(entry, range)) continue
    if (entry.kind === 'unavailable') tally.unavailable += 1
    else if (entry.status === 'approved') tally.approved += 1
    else tally.pending += 1
  }
  return tally
})
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
  timeZone: SGT_ZONE,
  plugins: [themePlugin, interactionPlugin, dayGridPlugin, timeGridPlugin, listPlugin],
  headerToolbar: {
    start: 'today prev,next title',
    end: 'dayGridMonth,timeGridWeek,listWeek'
  },
  initialView: 'dayGridMonth',
  height: 'auto',
  dayMaxEvents: false,
  eventDisplay: 'block',
  selectable: session.role === 'venue',
  selectMirror: true,
  unselectAuto: true,
  selectMinDistance: 4,
  events: [],
  datesSet(arg) {
    visibleRange.value = { start: arg.start.getTime(), end: arg.end.getTime() }
  },
  eventClassNames(arg) {
    return [arg.event.extendedProps.kind]
  },
  eventClick(arg) {
    const entry = arg.event.extendedProps
    if (entry.kind === 'draft') return
    if (entry.kind === 'unavailable') {
      openDetailAt(arg.el.getBoundingClientRect(), entry, true)
      return
    }
    openDetailAt(arg.el.getBoundingClientRect(), entry, true)
  },
  eventMouseEnter(arg) {
    if (arg.event.extendedProps.kind === 'draft') return
    openDetailAt(arg.el.getBoundingClientRect(), arg.event.extendedProps, false)
  },
  eventMouseLeave() {
    scheduleClose()
  },
  select(info) {
    ignoreDateClick = true
    applySelection(info.start, info.end, info.allDay)
    info.view.calendar.unselect()
    setTimeout(() => { ignoreDateClick = false }, 0)
  },
  dateClick(info) {
    if (ignoreDateClick || session.role !== 'venue') return
    const target = info.jsEvent?.target
    if (target?.closest?.('button, a, [data-kind]')) return
    const end = new Date(info.date.getTime())
    if (info.allDay) end.setUTCDate(end.getUTCDate() + 1)
    else end.setUTCMinutes(end.getUTCMinutes() + slotMinutes(info.view.calendar))
    applySelection(info.date, end, info.allDay)
  }
})

watch(
  () => [form.open, form.startsAt, form.endsAt],
  () => {
    paintEvents()
    const draft = currentDraft()
    if (draft) revealDraft(draft)
  }
)

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
  closeDetail()
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
      .map((booking) => {
        const snapshot = booking.eventSnapshot || {}
        return {
          id: booking.bookingId,
          kind: 'booking',
          title: snapshot.eventName || booking.eventId,
          eventId: booking.eventId,
          status: booking.status,
          startsAt: booking.startsAt,
          endsAt: booking.endsAt,
          setupStartsAt: booking.setupStartsAt,
          teardownEndsAt: booking.teardownEndsAt,
          client: snapshot.clientOrganisation || '',
          attendance: snapshot.expectedAttendance,
          layout: snapshot.layout || '',
          requirements: booking.requirementsSnapshot || snapshot.requiredFacilities || '',
          notes: booking.coordinatorNotes || '',
          hold: booking.hold,
          reverificationNote: booking.needsReverification ? booking.reverificationNote || '' : '',
          createdAt: booking.createdAt
        }
      })
    entries.value = [...blocks, ...bookings]
    paintEvents()
  } catch {
    loadError.value = 'Could not load this venue calendar.'
    return
  }
  await nextTick()
  if (!form.open) showNearbyMonth()
  await nextTick()
  revealFocusedBlock()
}

function currentDraft() {
  if (!form.open || form.id || !form.startsAt || !form.endsAt) return null
  const startsAt = toUtc(form.startsAt)
  const endsAt = toUtc(form.endsAt)
  if (!startsAt || !endsAt) return null
  const start = new Date(ensureZ(startsAt)).getTime()
  const end = new Date(ensureZ(endsAt)).getTime()
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return null
  return { startsAt, endsAt }
}

function paintEvents() {
  const events = entries.value.map(toCalendarEvent)
  const draft = currentDraft()
  if (draft) events.push(toDraftEvent(draft))
  calendarOptions.events = events
}

function toDraftEvent(range) {
  const start = new Date(ensureZ(range.startsAt))
  const end = new Date(ensureZ(range.endsAt))
  // Whole Singapore days: from midnight to 23:59.
  const wholeDays = toSgtInput(start).endsWith('T00:00') && toSgtInput(end).endsWith('T23:59')
  const event = {
    id: 'draft-selection',
    title: 'Selected',
    backgroundColor: '#fee2e2',
    borderColor: '#b91c1c',
    textColor: '#7f1d1d',
    classNames: ['draft-selection'],
    extendedProps: { kind: 'draft', id: 'draft' }
  }
  if (wholeDays) {
    const exclusiveEnd = new Date(end.getTime())
    exclusiveEnd.setUTCMinutes(exclusiveEnd.getUTCMinutes() + 1)
    event.allDay = true
    event.start = sgtDay(start)
    event.end = sgtDay(exclusiveEnd)
    return event
  }
  event.start = ensureZ(range.startsAt)
  event.end = ensureZ(range.endsAt)
  return event
}

function toCalendarEvent(entry) {
  const blocked = entry.kind === 'unavailable'
  const tone = blocked ? '#b91c1c' : entry.status === 'approved' ? '#15803d' : '#5b21b6'
  return {
    id: `${entry.kind}-${entry.id}`,
    title: blocked ? 'Unavailable' : entry.title,
    start: ensureZ(entry.startsAt),
    end: ensureZ(entry.endsAt),
    backgroundColor: tone,
    borderColor: tone,
    textColor: '#ffffff',
    extendedProps: entry
  }
}

function overlapsRange(entry, range) {
  const start = new Date(ensureZ(entry.startsAt)).getTime()
  const end = new Date(ensureZ(entry.endsAt)).getTime()
  return start < range.end && end > range.start
}

function showNearbyMonth() {
  const api = calendarRef.value?.getApi?.()
  if (!api) return
  const at = props.focusAt || (typeof route.query.at === 'string' ? route.query.at : '')
  if (at && !Number.isNaN(new Date(ensureZ(at)).getTime())) {
    api.gotoDate(ensureZ(at))
    return
  }
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

function revealFocusedBlock() {
  const at = props.focusAt || (typeof route.query.at === 'string' ? route.query.at : '')
  if (!at) return
  const moment = new Date(ensureZ(at)).getTime()
  if (Number.isNaN(moment)) return
  const blocks = entries.value.filter((entry) => entry.kind === 'unavailable')
  const match = blocks.find((entry) => new Date(ensureZ(entry.startsAt)).getTime() === moment)
    || blocks.find((entry) => {
      const start = new Date(ensureZ(entry.startsAt)).getTime()
      const end = new Date(ensureZ(entry.endsAt)).getTime()
      return start <= moment && end > moment
    })
  if (!match) return
  document.querySelector(`[data-testid="calendar-unavailable-${match.id}"]`)
    ?.scrollIntoView({ block: 'center' })
}

const detailRows = computed(() => {
  const entry = detail.entry
  if (!entry) return []
  if (entry.kind === 'unavailable') {
    return [
      ['Reason', entry.reason],
      ['Start', formatWhen(entry.startsAt)],
      ['End', formatWhen(entry.endsAt)],
      entry.note ? ['Note', entry.note] : null
    ].filter(Boolean).map(([label, value]) => ({ label, value }))
  }
  const rows = [
    ['Event', entry.eventId],
    ['Status', entry.status],
    ['Start', formatWhen(entry.startsAt)],
    ['End', formatWhen(entry.endsAt)]
  ]
  if (entry.setupStartsAt) rows.push(['Setup from', formatWhen(entry.setupStartsAt)])
  if (entry.teardownEndsAt) rows.push(['Clear by', formatWhen(entry.teardownEndsAt)])
  if (entry.client) rows.push(['Client', entry.client])
  if (entry.attendance !== undefined && entry.attendance !== null && entry.attendance !== '') {
    rows.push(['Attendance', String(entry.attendance)])
  }
  if (entry.layout) rows.push(['Layout', entry.layout])
  if (entry.requirements) rows.push(['Requirements', entry.requirements])
  if (entry.notes) rows.push(['Notes', entry.notes])
  if (entry.hold?.state === 'active') rows.push(['Hold', `Active until ${formatWhen(entry.hold.expiresAt)}`])
  else if (entry.hold?.state) rows.push(['Hold', entry.hold.state])
  if (entry.reverificationNote) rows.push(['Needs another check', entry.reverificationNote])
  return rows.map(([label, value]) => ({ label, value }))
})

function openDetailAt(rect, entry, pin) {
  if (detail.pinned && !pin && detail.entry?.id !== entry.id) return
  clearTimeout(hideTimer)
  const cardWidth = 300
  let left = rect.left
  if (left + cardWidth > window.innerWidth - 16) left = window.innerWidth - cardWidth - 16
  if (left < 16) left = 16
  let top = rect.bottom + 8
  if (top + 260 > window.innerHeight - 16) top = Math.max(16, rect.top - 268)
  detail.entry = entry
  detail.top = top
  detail.left = left
  if (pin) detail.pinned = true
}

function openDetail(domEvent, entry, pin) {
  openDetailAt(domEvent.currentTarget.getBoundingClientRect(), entry, pin)
}

function selectBlock(id, domEvent) {
  const entry = entryById(id)
  if (entry && domEvent) openDetail(domEvent, entry, true)
}

function holdDetail() {
  clearTimeout(hideTimer)
  detail.overCard = true
}

function releaseDetail() {
  detail.overCard = false
  scheduleClose()
}

function scheduleClose() {
  if (detail.pinned) return
  clearTimeout(hideTimer)
  hideTimer = setTimeout(() => {
    if (!detail.overCard && !detail.pinned) detail.entry = null
  }, 200)
}

function closeDetail() {
  clearTimeout(hideTimer)
  detail.pinned = false
  detail.overCard = false
  detail.entry = null
}

function formatWhen(value) {
  if (!value) return ''
  return formatSgt(value) || String(value)
}

function entryById(id) {
  return entries.value.find((entry) => entry.id === id)
}

let ignoreDateClick = false

function applySelection(start, end, allDay) {
  if (session.role !== 'venue') return
  const finish = new Date(end.getTime())
  if (allDay) finish.setUTCMinutes(finish.getUTCMinutes() - 1)
  if (finish.getTime() <= start.getTime()) return
  if (!form.open) startCreate()
  form.startsAt = toSgtInput(start)
  form.endsAt = toSgtInput(finish)
}

function slotMinutes(calendar) {
  const duration = calendar?.getOption?.('slotDuration')
  if (!duration) return 30
  if (typeof duration === 'string') {
    const parts = duration.split(':').map(Number)
    return (parts[0] || 0) * 60 + (parts[1] || 0) || 30
  }
  if (typeof duration.milliseconds === 'number' && duration.milliseconds > 0) {
    return Math.round(duration.milliseconds / 60000)
  }
  return (duration.hours || 0) * 60 + (duration.minutes || 0) || 30
}

function closeForm() {
  form.open = false
}

function changeVenue() {
  closeForm()
  load()
}

function revealDraft(range) {
  const api = calendarRef.value?.getApi?.()
  const view = visibleRange.value
  if (!api || !view) return
  const start = new Date(ensureZ(range.startsAt)).getTime()
  const end = new Date(ensureZ(range.endsAt)).getTime()
  if (start < view.end && end > view.start) return
  api.gotoDate(ensureZ(range.startsAt))
}

function startCreate() {
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
  closeDetail()
  Object.assign(form, {
    open: true,
    id,
    startsAt: toSgtInput(entry.startsAt),
    endsAt: toSgtInput(entry.endsAt),
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
    closeForm()
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
    if (form.id === id) closeForm()
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

// The form shows and takes Singapore time; the server stores UTC.
function toUtc(value) {
  return fromSgtInput(value)
}
</script>

<style scoped>
.venue-calendar { width: 100%; }
.back { color: #c4b5fd; text-decoration: none; font-size: 14px; }
.heading { margin: 0 0 14px; }
h1 { margin: 0; font-size: 28px; line-height: 1.15; }
.venue-pick {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 420px;
  font-size: 14px;
}
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.layout:has(.panel) { grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr); }
.calendar-column { min-width: 0; }
.reverify-banner {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fef3c7;
  color: #92400e;
  font-size: 0.9rem;
}
.calendar-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  margin: 0 0 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ece6f5;
}
.legend {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 0;
  padding: 0;
  list-style: none;
  color: #1c1233;
  font-size: 13px;
  font-weight: 650;
}
.legend li { display: flex; align-items: center; gap: 6px; }
.count {
  min-width: 1.4em;
  padding: 1px 6px;
  border-radius: 999px;
  background: #f4f0fb;
  color: #1c1233;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: center;
}
.swatch {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  flex-shrink: 0;
}
.swatch.pending { background: #5b21b6; }
.swatch.approved { background: #15803d; }
.swatch.unavailable { background: #b91c1c; }
.event-body {
  cursor: pointer;
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
.event-body[data-kind='unavailable'] { background: #b91c1c; }
.event-body[data-kind='draft'] {
  color: #7f1d1d;
  background: #fee2e2;
  border: 2px dashed #b91c1c;
  pointer-events: none;
}
.calendar-shell :deep(.draft-selection) {
  pointer-events: none !important;
  background: #fee2e2 !important;
  border: 2px dashed #b91c1c !important;
  box-shadow: none !important;
}
.event-body[data-kind='booking'] { background: #5b21b6; }
.event-body[data-kind='booking'][data-status='approved'] { background: #15803d; }
.kind { text-transform: capitalize; color: #fff7ed; }
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
.hint { margin: 0; color: var(--muted, #b7a8d4); font-size: 13px; line-height: 1.4; }
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
.mark-btn, .ghost-btn {
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
.ghost-btn {
  color: #f3eeff;
  background: #2a1458;
  border: 1px solid #c4b5fd;
}
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
.calendar-shell :deep([role='tab']) {
  margin: 0 0 0 10px !important;
}
.calendar-shell :deep([role='tab']:first-child) {
  margin-left: 0 !important;
}
.calendar-shell :deep([aria-selected='true']) {
  color: #fff;
  background: #5b21b6;
  border-color: #5b21b6;
}
.calendar-shell .mark-btn {
  color: #fff;
  background: #6d28d9;
  border-color: #6d28d9;
}
.calendar-shell :deep(a),
.calendar-shell :deep(h2) {
  color: #1c1233;
}
.detail-card {
  position: fixed;
  z-index: 80;
  width: 300px;
  max-height: min(360px, calc(100vh - 32px));
  overflow: auto;
  padding: 12px 14px;
  color: #f3eeff;
  background: #1a1030;
  border: 1px solid #c4b5fd;
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
}
.detail-card header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 10px;
}
.detail-card header strong { font-size: 15px; line-height: 1.3; }
.detail-card header button {
  flex-shrink: 0;
  color: #f3eeff;
  background: #2a1458;
  border: 1px solid #c4b5fd;
  border-radius: 8px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 650;
}
.detail-card dl { margin: 0; }
.detail-card div { margin-bottom: 8px; }
.detail-card div:last-child { margin-bottom: 0; }
.detail-card dt { color: #c4b5fd; font-size: 11px; font-weight: 650; text-transform: uppercase; letter-spacing: 0.03em; }
.detail-card dd { margin: 2px 0 0; color: #f3eeff; font-size: 13px; line-height: 1.35; white-space: pre-wrap; }
.detail-actions { display: flex; gap: 8px; margin-top: 12px; }
.detail-actions button {
  color: #f3eeff;
  background: #2a1458;
  border: 1px solid #c4b5fd;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 650;
}
.detail-actions .danger { color: #ffd0d0; border-color: #ffb4b4; }
@media (max-width: 900px) {
  .layout, .layout:has(.panel) { grid-template-columns: 1fr; }
  .calendar-bar { flex-wrap: wrap; }
  .venue-pick { max-width: none; }
}
</style>
