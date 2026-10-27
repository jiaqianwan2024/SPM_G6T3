<template>
  <!-- SPM-108: a venue's calendar, so internal staff can tell at a glance when it could be requested. -->
  <div class="venue-calendar" data-testid="venue-calendar" :data-view="view">
    <router-link v-if="!embedded" class="back" to="/app?tab=Venue%20Calendar">All venues</router-link>

    <header class="heading">
      <label v-if="embedded" class="venue-pick">
        Venue
        <select v-model="venueId" @change="changeVenue">
          <option v-for="item in venues" :key="item.venueId" :value="item.venueId">{{ item.name }}</option>
        </select>
      </label>
      <h1 v-else>{{ venueName || 'Venue' }}</h1>
    </header>

    <p v-if="loadError" class="error">{{ loadError }}</p>

    <div v-else class="layout">
      <div class="calendar-column">
        <div class="calendar-shell">
          <p v-if="needsRecheck" class="reverify-banner" data-testid="calendar-reverify">
            A booking on this calendar needs re-verification.
          </p>
          <div class="calendar-toolbar">
            <div class="nav">
              <button type="button" class="tool-btn" data-testid="calendar-today" @click="calendarApi()?.today()">Today</button>
              <button type="button" class="tool-btn icon" data-testid="calendar-prev" aria-label="Previous" @click="calendarApi()?.prev()">‹</button>
              <button type="button" class="tool-btn icon" data-testid="calendar-next" aria-label="Next" @click="calendarApi()?.next()">›</button>
              <h2 class="range-title" data-testid="calendar-title">{{ title }}</h2>
            </div>
            <div class="views" role="group" aria-label="Calendar view">
              <button
                v-for="option in VIEWS"
                :key="option.view"
                type="button"
                class="tool-btn"
                :class="{ active: view === option.view }"
                :aria-pressed="view === option.view"
                :data-testid="`calendar-view-${option.view}`"
                @click="changeView(option.view)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
          <div class="calendar-bar">
            <ul class="legend">
              <li v-for="item in KINDS" :key="item.kind">
                <span class="swatch" :class="`kind-${item.kind}`"></span>{{ item.label }}
                <span class="count">{{ counts[item.kind] }}</span>
              </li>
              <li><span class="swatch outside"></span>Outside opening hours</li>
            </ul>
            <button v-if="canWrite" type="button" class="mark-btn" data-testid="mark-unavailable" @click="startCreate">
              Mark unavailable
            </button>
          </div>
          <p v-if="loaded" class="hours" data-testid="calendar-opening-hours">
            Opening hours (SGT): {{ hoursSummary }}. Times outside them are unavailable.
          </p>
          <p v-if="loaded && !visibleCount" class="empty" data-testid="venue-calendar-empty">
            Nothing is booked, requested, held or blocked at {{ venueName || 'this venue' }} in this {{ view }}.
          </p>
          <FullCalendar ref="calendarRef" :options="calendarOptions">
            <template #dayCellTopContent="arg">
              <span class="day-top">
                <span
                  v-if="closedOn(arg.date)"
                  class="hours-tag"
                  data-testid="calendar-outside-hours"
                  title="The venue is closed all day"
                >Closed</span>
                <span class="day-number">{{ arg.dayNumberText }}</span>
              </span>
            </template>
            <template #eventContent="arg">
              <div
                v-if="arg.event.extendedProps.kind === 'unavailable'"
                class="event-body kind-unavailable"
                :data-testid="`calendar-unavailable-${arg.event.extendedProps.id}`"
                data-kind="unavailable"
                @mouseenter="openDetail($event, arg.event.extendedProps, false)"
                @mouseleave="scheduleClose"
                @click.stop="selectBlock(arg.event.extendedProps.id, $event)"
              >
                <span class="kind-tag" data-testid="calendar-kind-unavailable" data-kind="unavailable">Unavailable</span>
                <span class="line">{{ arg.event.extendedProps.reason }}</span>
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
                :class="[`kind-${arg.event.extendedProps.kind}`, { 'in-time-grid': inTimeGrid(arg) }]"
                data-kind="booking"
                :data-status="arg.event.extendedProps.status"
                @mouseenter="openDetail($event, arg.event.extendedProps, false)"
                @mouseleave="scheduleClose"
                @click.stop="openEntry(arg.event.extendedProps)"
              >
                <template v-if="inTimeGrid(arg)">
                  <span class="band setup" :style="{ height: bandShare(arg.event.extendedProps, 'setup') }" title="Setup"></span>
                  <span class="band turnaround" :style="{ height: bandShare(arg.event.extendedProps, 'turnaround') }" title="Turnaround"></span>
                </template>
                <div
                  class="entry"
                  :data-testid="`calendar-booking-${arg.event.extendedProps.id}`"
                  :data-kind="arg.event.extendedProps.kind"
                >
                  <span
                    class="kind-tag"
                    :data-testid="`calendar-kind-${arg.event.extendedProps.kind}`"
                    :data-kind="arg.event.extendedProps.kind"
                  >{{ kindLabel(arg.event.extendedProps.kind) }}</span>
                  <strong>{{ arg.event.extendedProps.title }}</strong>
                  <span v-if="arg.event.extendedProps.client" class="line">{{ arg.event.extendedProps.client }}</span>
                  <span class="line time">{{ eventTimes(arg.event.extendedProps) }}</span>
                </div>
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
        <div v-else-if="detail.entry.kind !== 'unavailable'" class="detail-actions">
          <button type="button" data-testid="calendar-open-entry" @click="openEntry(detail.entry)">
            {{ opensRequest(detail.entry) ? 'Open request' : 'Open event' }}
          </button>
        </div>
      </aside>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FullCalendar from '@fullcalendar/vue3'
import themePlugin from '@fullcalendar/vue3/themes/monarch'
import interactionPlugin from '@fullcalendar/vue3/interaction'
import dayGridPlugin from '@fullcalendar/vue3/daygrid'
import timeGridPlugin from '@fullcalendar/vue3/timegrid'

import '@fullcalendar/vue3/skeleton.css'
import '@fullcalendar/vue3/themes/monarch/theme.css'
import '@fullcalendar/vue3/themes/monarch/palettes/purple.css'

import {
  cancelVenueUnavailability,
  createVenueUnavailability,
  getVenueCalendar,
  getVenues,
  updateVenueUnavailability
} from '../../api/venueService.js'
import { session } from '../../store/session.js'
import {
  SGT_ZONE,
  formatSgt,
  formatSgtRange,
  formatSgtTime,
  fromSgtInput,
  parseServerTime,
  sgtDay,
  toSgtInput
} from '../../utils/datetime.js'

const props = defineProps({
  focusVenue: { type: String, default: '' },
  focusAt: { type: String, default: '' },
  focusFrom: { type: String, default: '' },
  focusTo: { type: String, default: '' }
})
const reasons = ['maintenance', 'renovation', 'safety issue', 'internal activity', 'other']
// SPM-108 AC2: each kind has its own colour and its own label, so none is told apart by colour alone.
const KINDS = [
  { kind: 'confirmed', label: 'Confirmed' },
  { kind: 'pending', label: 'Pending request' },
  { kind: 'hold', label: 'On hold' },
  { kind: 'expired-hold', label: 'Hold expired' },
  { kind: 'unavailable', label: 'Unavailable' }
]
const VIEWS = [
  { view: 'week', label: 'Week', type: 'timeGridWeek' },
  { view: 'month', label: 'Month', type: 'dayGridMonth' }
]
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const DAY_MS = 24 * 60 * 60 * 1000

const route = useRoute()
const router = useRouter()
const embedded = computed(() => route.name !== 'venue-calendar')
const venueId = ref(props.focusVenue || (typeof route.params.id === 'string' ? route.params.id : ''))
const venues = ref([])
const venueName = ref('')
const openingHours = ref([])
const entries = ref([])
const loaded = ref(false)
const needsRecheck = computed(() => entries.value.some((entry) => entry.reverificationNote))
const visibleRange = ref(null)
const view = ref(startView())
const title = ref('')
const loadError = ref('')
const calendarRef = ref(null)
const detail = reactive({ entry: null, pinned: false, overCard: false, top: 0, left: 0 })
let hideTimer = 0
const canWrite = computed(() => session.role === 'venue')
const visibleEntries = computed(() => {
  const range = visibleRange.value
  return range ? entries.value.filter((entry) => overlapsRange(entry, range)) : entries.value
})
const visibleCount = computed(() => visibleEntries.value.length)
const counts = computed(() => {
  const tally = Object.fromEntries(KINDS.map((item) => [item.kind, 0]))
  for (const entry of visibleEntries.value) tally[entry.kind] += 1
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
  plugins: [themePlugin, interactionPlugin, dayGridPlugin, timeGridPlugin],
  headerToolbar: false,
  initialView: VIEWS.find((option) => option.view === view.value).type,
  initialDate: startDate(),
  height: 'auto',
  dayMaxEvents: false,
  eventDisplay: 'block',
  // SPM-108 AC5: the week view shades every time outside the venue's opening hours.
  businessHours: false,
  nonBusinessHoursClass: 'outside-hours',
  selectable: session.role === 'venue',
  selectMirror: true,
  unselectAuto: true,
  selectMinDistance: 4,
  events: [],
  datesSet(arg) {
    visibleRange.value = { start: arg.start.getTime(), end: arg.end.getTime() }
    view.value = arg.view.type === 'timeGridWeek' ? 'week' : 'month'
    title.value = arg.view.title
  },
  eventClass(arg) {
    return [`kind-${arg.event.extendedProps.kind}`]
  },
  dayCellClass(arg) {
    return closedOn(arg.date) ? ['closed-day'] : []
  },
  eventClick(arg) {
    const entry = arg.event.extendedProps
    if (entry.kind === 'draft') return
    if (entry.kind === 'unavailable') {
      openDetailAt(arg.el.getBoundingClientRect(), entry, true)
      return
    }
    openEntry(entry)
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

// A link may open the calendar on a moment (`at`) or a range (`from`, `to`). A range of
// a week or less opens in the week view; otherwise the calendar opens on this month.
function startView() {
  const from = focusMoment(props.focusFrom)
  const to = focusMoment(props.focusTo)
  return from && to && to - from <= 7 * DAY_MS ? 'week' : 'month'
}

function startDate() {
  const value = props.focusFrom || props.focusAt
  return focusMoment(value) ? focusMoment(value).toISOString() : undefined
}

// A link's date: "YYYY-MM-DD" is a Singapore date; anything else is a server time.
function focusMoment(value) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value || '')) {
    const date = new Date(`${value}T00:00:00+08:00`)
    return Number.isNaN(date.getTime()) ? null : date
  }
  return parseServerTime(value)
}

// SPM-108 AC7: every open reads the calendar afresh, so decisions, holds and blocks made since show.
async function load() {
  if (!venueId.value) return
  loadError.value = ''
  closeDetail()
  try {
    const { data } = await getVenueCalendar(venueId.value)
    venueName.value = data.venueName
    openingHours.value = data.operatingHours || []
    entries.value = data.entries.map(toEntry)
    calendarOptions.businessHours = businessHours(openingHours.value)
    paintEvents()
    loaded.value = true
  } catch {
    loadError.value = 'Could not load this venue calendar.'
    return
  }
  await nextTick()
  revealFocusedBlock()
}

function toEntry(item) {
  if (item.kind === 'unavailable') {
    const block = item.unavailability || {}
    return {
      id: item.id,
      kind: 'unavailable',
      reason: block.reason,
      note: block.note,
      startsAt: item.startsAt,
      endsAt: item.endsAt,
      createdAt: block.createdAt
    }
  }
  const booking = item.booking || {}
  const snapshot = booking.eventSnapshot || {}
  return {
    id: item.id,
    kind: item.kind,
    title: item.eventName || item.eventId,
    eventId: item.eventId,
    status: booking.status,
    // SPM-108 AC3: the entry spans the occupied window; the event's advertised times sit inside it.
    startsAt: item.startsAt,
    endsAt: item.endsAt,
    eventStartsAt: item.eventStartsAt,
    eventEndsAt: item.eventEndsAt,
    client: item.clientOrganisation || '',
    attendance: snapshot.expectedAttendance,
    layout: snapshot.layout || '',
    requirements: booking.requirementsSnapshot || snapshot.requiredFacilities || '',
    notes: booking.coordinatorNotes || '',
    hold: booking.hold,
    reverificationNote: booking.needsReverification ? booking.reverificationNote || 'Needs another check' : ''
  }
}

// Opening hours are Singapore wall-clock times, the calendar's own time zone.
function businessHours(hours) {
  return hours
    .filter((item) => DAYS.includes(item.day))
    .map((item) => ({ daysOfWeek: [DAYS.indexOf(item.day)], startTime: item.opens, endTime: item.closes }))
}

// FullCalendar's day dates carry the calendar's wall-clock date in their UTC fields.
function hoursFor(date) {
  return openingHours.value.filter((item) => item.day === DAYS[date.getUTCDay()])
}

function closedOn(date) {
  return loaded.value && !hoursFor(date).length
}

// "Mon–Fri 08:00–18:00 · Sat–Sun closed": days in a row with the same hours share one part.
const hoursSummary = computed(() => {
  const groups = []
  for (const day of [...DAYS.slice(1), DAYS[0]]) {
    const hours = openingHours.value
      .filter((item) => item.day === day)
      .map((item) => `${item.opens}–${item.closes}`)
      .join(', ') || 'closed'
    const last = groups[groups.length - 1]
    if (last?.hours === hours) last.days.push(day)
    else groups.push({ days: [day], hours })
  }
  return groups
    .map(({ days, hours }) => `${days.length > 1 ? `${days[0]}–${days[days.length - 1]}` : days[0]} ${hours}`)
    .join(' · ')
})

function calendarApi() {
  return calendarRef.value?.getApi?.()
}

function changeView(next) {
  calendarApi()?.changeView(VIEWS.find((option) => option.view === next).type)
}

function inTimeGrid(arg) {
  return arg.view.type.startsWith('timeGrid')
}

// The share of the block that setup (before the event) or turnaround (after it) takes.
function bandShare(entry, part) {
  const start = parseServerTime(entry.startsAt)?.getTime()
  const end = parseServerTime(entry.endsAt)?.getTime()
  const eventStart = parseServerTime(entry.eventStartsAt)?.getTime()
  const eventEnd = parseServerTime(entry.eventEndsAt)?.getTime()
  if ([start, end, eventStart, eventEnd].some((value) => value === undefined) || end <= start) return '0%'
  const span = part === 'setup' ? eventStart - start : end - eventEnd
  return `${Math.max(0, Math.min(100, (span / (end - start)) * 100))}%`
}

function kindLabel(kind) {
  return KINDS.find((item) => item.kind === kind)?.label || kind
}

function eventTimes(entry) {
  return `${formatSgtTime(entry.eventStartsAt)}–${formatSgtTime(entry.eventEndsAt)}`
}

// SPM-108 AC4: an entry opens its record. Venue Staff work holds from the pending requests;
// everyone else, and every other booking, opens the event.
function opensRequest(entry) {
  return session.role === 'venue' && (entry.kind === 'hold' || entry.kind === 'expired-hold')
}

function openEntry(entry) {
  closeDetail()
  if (opensRequest(entry)) {
    router.push({ name: 'dashboard', query: { tab: 'Booking Requests', status: 'pending', booking: entry.id } })
    return
  }
  router.push({ name: 'event-detail', params: { id: entry.eventId } })
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

const TONES = {
  confirmed: '#15803d',
  pending: '#5b21b6',
  hold: '#b45309',
  'expired-hold': '#6b7280',
  unavailable: '#b91c1c'
}

function toCalendarEvent(entry) {
  const tone = TONES[entry.kind]
  return {
    id: `${entry.kind}-${entry.id}`,
    title: entry.kind === 'unavailable' ? 'Unavailable' : entry.title,
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

function revealFocusedBlock() {
  const at = props.focusAt
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
    ['Status', kindLabel(entry.kind)],
    ['Client', entry.client || 'Not given'],
    ['Event time', formatSgtRange(entry.eventStartsAt, entry.eventEndsAt)],
    ['Occupied, with setup and turnaround', formatSgtRange(entry.startsAt, entry.endsAt)]
  ]
  if (entry.hold?.state === 'active') rows.push(['Hold', `Active until ${formatWhen(entry.hold.expiresAt)}`])
  else if (entry.hold?.state === 'expired') rows.push(['Hold', `Expired ${formatWhen(entry.hold.expiresAt)}`])
  if (entry.attendance !== undefined && entry.attendance !== null && entry.attendance !== '') {
    rows.push(['Attendance', String(entry.attendance)])
  }
  if (entry.layout) rows.push(['Layout', entry.layout])
  if (entry.requirements) rows.push(['Requirements', entry.requirements])
  if (entry.notes) rows.push(['Notes', entry.notes])
  if (entry.reverificationNote) rows.push(['Needs another check', entry.reverificationNote])
  return rows.map(([label, value]) => ({ label, value }))
})

function openDetailAt(rect, entry, pin) {
  if (detail.pinned && !pin && detail.entry?.id !== entry.id) return
  clearTimeout(hideTimer)
  const cardWidth = 300
  const cardHeight = 360
  let left = rect.left
  let top = rect.bottom + 8
  // Below the entry, else above it, else beside it: the card never covers the entry it describes.
  if (top + cardHeight > window.innerHeight - 16) {
    if (rect.top - cardHeight - 8 >= 16) {
      top = rect.top - cardHeight - 8
    } else {
      top = Math.max(16, Math.min(rect.top, window.innerHeight - cardHeight - 16))
      left = rect.right + 8 + cardWidth <= window.innerWidth - 16 ? rect.right + 8 : rect.left - cardWidth - 8
    }
  }
  if (left + cardWidth > window.innerWidth - 16) left = window.innerWidth - cardWidth - 16
  if (left < 16) left = 16
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
  const api = calendarApi()
  const visible = visibleRange.value
  if (!api || !visible) return
  const start = new Date(ensureZ(range.startsAt)).getTime()
  const end = new Date(ensureZ(range.endsAt)).getTime()
  if (start < visible.end && end > visible.start) return
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
  border-radius: var(--radius);
  background: #fef3c7;
  color: #92400e;
  font-size: 0.9rem;
}
.calendar-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 12px;
}
.nav, .views { display: flex; align-items: center; gap: 8px; }
.range-title { margin: 0 0 0 6px; font-size: 18px; color: #1c1233; }
.tool-btn {
  padding: 6px 12px;
  color: #1c1233;
  background: #f4f0fb;
  border: 1px solid #d9d0ea;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}
.tool-btn.icon { padding: 6px 10px; font-size: 16px; line-height: 1; }
.tool-btn.active { color: #fff; background: #5b21b6; border-color: #5b21b6; }
.calendar-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 0 0 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ece6f5;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
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
.swatch.kind-confirmed { background: #15803d; }
.swatch.kind-pending { background: #5b21b6; }
.swatch.kind-hold { background: #b45309; }
.swatch.kind-expired-hold { background: #f3f4f6; border: 2px dashed #6b7280; }
.swatch.kind-unavailable { background: #b91c1c; }
.swatch.outside { background: repeating-linear-gradient(135deg, #e5e7eb 0 3px, #f9fafb 3px 6px); border: 1px solid #d1d5db; }
.empty {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: #f4f0fb;
  color: #1c1233;
  font-size: 13px;
}
.day-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; width: 100%; }
.hours-tag {
  padding: 1px 6px;
  border-radius: 999px;
  background: #e5e7eb;
  color: #374151;
  font-size: 11px;
  font-weight: 600;
}
.hours { margin: 0 0 12px; color: #4b5563; font-size: 13px; }
.calendar-shell :deep(.closed-day),
.calendar-shell :deep(.outside-hours) {
  background: repeating-linear-gradient(135deg, #e5e7eb 0 3px, #f9fafb 3px 6px);
}
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
  overflow: hidden;
}
.event-body.in-time-grid { height: 100%; }
.event-body.kind-confirmed { background: #15803d; }
.event-body.kind-pending { background: #5b21b6; }
.event-body.kind-hold { background: #b45309; }
.event-body.kind-expired-hold { background: #f3f4f6; color: #374151; border: 2px dashed #6b7280; }
.event-body.kind-unavailable { background: #b91c1c; }
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
.calendar-shell :deep(.kind-expired-hold) { background: #f3f4f6 !important; border-color: #6b7280 !important; }
.entry { position: relative; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.kind-tag {
  align-self: flex-start;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.22);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.kind-expired-hold .kind-tag { background: #e5e7eb; }
.line { font-weight: 600; opacity: 0.95; }
.time { font-variant-numeric: tabular-nums; }
/* SPM-108 AC3: setup and turnaround are the hatched ends of a booking's occupied window. */
.band {
  position: absolute;
  left: 0;
  right: 0;
  background: repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.28) 0 3px, transparent 3px 7px);
  pointer-events: none;
}
.band.setup { top: 0; border-bottom: 1px dashed rgba(255, 255, 255, 0.7); }
.band.turnaround { bottom: 0; border-top: 1px dashed rgba(255, 255, 255, 0.7); }
.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--hairline, rgba(243, 238, 255, 0.16));
  border-radius: var(--radius);
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
  border-radius: var(--radius);
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
  border-radius: var(--radius);
  padding: 12px 16px 16px;
  overflow: auto;
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
  border-radius: var(--radius);
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
