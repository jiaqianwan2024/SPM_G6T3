<template>
  <!-- SPM-8: Venue Staff review submitted venue booking requests and approve them. -->
  <div class="booking-requests" data-testid="booking-requests">
    <div class="toolbar">
      <div class="filters">
        <button
          v-for="option in STATUSES"
          :key="option.value"
          type="button"
          class="filter-btn"
          :class="{ active: status === option.value }"
          :data-testid="`booking-filter-${option.value}`"
          @click="status = option.value"
        >
          {{ option.label }}
        </button>
      </div>
      <label class="venue-filter">
        Venue
        <select v-model="venueId" data-testid="booking-venue-filter">
          <option value="">All venues</option>
          <option v-for="venue in venues" :key="venue.venueId" :value="venue.venueId">{{ venue.name }}</option>
        </select>
      </label>
    </div>

    <p class="hint">
      Oldest request first: requests are handled in the order they were submitted. All times are in UTC.
    </p>

    <p v-if="notice" class="notice" data-testid="booking-approved-notice">{{ notice }}</p>

    <p v-if="loading" class="empty-note">Loading booking requests…</p>
    <p v-else-if="loadError" class="form-error" data-testid="booking-requests-error">{{ loadError }}</p>
    <p v-else-if="!bookings.length" class="empty-note" data-testid="booking-requests-empty">
      {{ status === 'pending' ? 'No pending booking requests.' : 'No approved bookings.' }}
    </p>

    <div v-else class="booking-list">
      <article
        v-for="booking in bookings"
        :key="booking.bookingId"
        class="booking-card"
        :data-testid="`booking-request-${booking.bookingId}`"
      >
        <div class="card-top">
          <div class="name-row">
            <span class="event-name">{{ eventName(booking) }}</span>
            <span
              v-if="competition[booking.bookingId]"
              class="tag competing"
              :data-testid="`booking-competing-${booking.bookingId}`"
            >
              Competing request {{ competition[booking.bookingId].position }} of
              {{ competition[booking.bookingId].size }}
            </span>
            <span
              v-if="booking.hold?.state === 'active'"
              class="tag held"
              :data-testid="`booking-hold-${booking.bookingId}`"
            >
              On hold until {{ moment(booking.hold.expiresAt) }}
            </span>
            <span
              v-else-if="booking.hold?.state === 'expired'"
              class="tag expired"
              :data-testid="`booking-hold-${booking.bookingId}`"
            >
              Hold expired {{ moment(booking.hold.expiresAt) }}
            </span>
          </div>
          <span class="status-pill" data-testid="booking-status">{{ booking.status }}</span>
        </div>

        <div class="venue">{{ booking.venueName || booking.venueId }}</div>
        <div v-if="booking.eventSnapshot?.clientOrganisation" class="org">
          {{ booking.eventSnapshot.clientOrganisation }}
        </div>

        <dl>
          <div>
            <dt>Event</dt>
            <dd data-testid="booking-starts-at">{{ span(booking.startsAt, booking.endsAt) }}</dd>
          </div>
          <div>
            <dt>Venue occupied</dt>
            <dd data-testid="booking-occupied">
              {{ span(booking.setupStartsAt, booking.teardownEndsAt) }}, including setup and turnaround
            </dd>
          </div>
          <div>
            <dt>Requirements</dt>
            <dd data-testid="booking-requirements">{{ requirements(booking) }}</dd>
          </div>
          <div v-if="booking.coordinatorNotes">
            <dt>Coordinator notes</dt>
            <dd>{{ booking.coordinatorNotes }}</dd>
          </div>
          <div v-if="booking.warnings?.length">
            <dt>Warnings accepted</dt>
            <dd>{{ booking.warnings.join(' ') }}</dd>
          </div>
          <div>
            <dt>Submitted</dt>
            <dd data-testid="booking-submitted-at">{{ moment(booking.createdAt) }}</dd>
          </div>
        </dl>

        <div v-if="booking.status === 'approved'" class="approved">
          <p :data-testid="`booking-approved-by-${booking.bookingId}`">
            Approved by {{ booking.reviewedByName || booking.reviewedBy }} on {{ moment(booking.reviewedAt) }}
          </p>
          <p class="locked">Confirmed. The venue is reserved for the occupied window above.</p>
          <p v-if="booking.decisionReason" class="note">Note: {{ booking.decisionReason }}</p>
        </div>

        <div v-else-if="booking.status === 'pending'" class="actions">
          <input
            v-model="notes[booking.bookingId]"
            type="text"
            maxlength="500"
            placeholder="Note (optional)"
            :data-testid="`booking-approve-note-${booking.bookingId}`"
          />
          <button
            type="button"
            class="btn btn-solid"
            :disabled="busyId === booking.bookingId"
            :data-testid="`booking-approve-${booking.bookingId}`"
            @click="approve(booking)"
          >
            {{ busyId === booking.bookingId ? 'Approving…' : 'Approve' }}
          </button>
        </div>
        <p v-if="errors[booking.bookingId]" class="row-error" :data-testid="`booking-error-${booking.bookingId}`">
          {{ errors[booking.bookingId] }}
        </p>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { approveVenueBooking, getVenueBookings, getVenues } from '../../api/venueService.js'

const STATUSES = [
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
]

const status = ref('pending')
const venueId = ref('')
const venues = ref([])
const bookings = ref([])
const loading = ref(true)
const loadError = ref('')
const notice = ref('')
const busyId = ref('')
const notes = reactive({})
const errors = reactive({})

// Booking times are UTC and come without a zone marker.
const dayFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' })
const timeFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })

function utc(value) {
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`)
}

function moment(value) {
  const when = utc(value)
  return `${dayFormat.format(when)}, ${timeFormat.format(when)} UTC`
}

function span(start, end) {
  const [from, to] = [utc(start), utc(end)]
  const sameDay = dayFormat.format(from) === dayFormat.format(to)
  return sameDay
    ? `${dayFormat.format(from)}, ${timeFormat.format(from)} to ${timeFormat.format(to)} UTC`
    : `${moment(start)} to ${moment(end)}`
}

function eventName(booking) {
  const name = booking.eventSnapshot?.eventName
  return name ? `"${name}"` : `Event ${booking.eventId}`
}

function requirements(booking) {
  const event = booking.eventSnapshot || {}
  const parts = [
    event.expectedAttendance ? `${event.expectedAttendance} attendees` : '',
    event.layout ? `${event.layout} layout` : '',
    event.requiredFacilities ? `Facilities: ${event.requiredFacilities}` : '',
    event.accessibilityNeeds ? `Accessibility: ${event.accessibilityNeeds}` : '',
    (booking.requirementsSnapshot || '').trim(),
  ]
    .map((part) => part.replace(/\.+$/, ''))
    .filter(Boolean)
  return parts.length ? `${parts.join('. ')}.` : 'None stated'
}

// SPM-8 AC11: pending requests for the same venue whose occupied windows overlap
// compete for it. The list is already oldest first, so a request's position among
// the requests it competes with is its place in that order. Worked out once per
// load, by venue, so a long queue stays quick to draw.
const competition = computed(() => {
  const byVenue = {}
  for (const row of bookings.value) {
    if (row.status !== 'pending') continue
    const window = { row, from: utc(row.setupStartsAt).getTime(), to: utc(row.teardownEndsAt).getTime() }
    ;(byVenue[row.venueId] ||= []).push(window)
  }
  const result = {}
  for (const windows of Object.values(byVenue)) {
    for (const mine of windows) {
      const group = windows.filter((other) => other === mine || (mine.from < other.to && other.from < mine.to))
      if (group.length > 1) {
        result[mine.row.bookingId] = { position: group.indexOf(mine) + 1, size: group.length }
      }
    }
  }
  return result
})

function message(err, fallback) {
  const detail = err.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

// Only the newest load may fill the list, so a slow earlier answer never replaces it.
let latestLoad = 0

async function load() {
  const mine = ++latestLoad
  loading.value = true
  try {
    const params = { status: status.value }
    if (venueId.value) params.venueId = venueId.value
    const { data } = await getVenueBookings(params)
    if (mine !== latestLoad) return
    bookings.value = data
    loadError.value = ''
  } catch {
    if (mine === latestLoad) loadError.value = 'Unable to load the booking requests. Please try again.'
  } finally {
    if (mine === latestLoad) loading.value = false
  }
}

async function loadVenues() {
  try {
    const { data } = await getVenues(true)
    venues.value = data
  } catch {
    venues.value = []
  }
}

async function approve(booking) {
  busyId.value = booking.bookingId
  errors[booking.bookingId] = ''
  notice.value = ''
  try {
    const note = (notes[booking.bookingId] || '').trim()
    const { data } = await approveVenueBooking(booking.bookingId, note || null)
    notice.value =
      `Approved. ${data.venueName || data.venueId} is reserved for ${eventName(data)} ` +
      `from ${span(data.setupStartsAt, data.teardownEndsAt)}.`
    await load()
  } catch (err) {
    errors[booking.bookingId] = message(err, 'Unable to approve this request. Please try again.')
  } finally {
    busyId.value = ''
  }
}

watch([status, venueId], () => {
  notice.value = ''
  load()
})
onMounted(() => {
  loadVenues()
  load()
})
</script>

<style scoped>
.booking-requests { display: flex; flex-direction: column; gap: 14px; width: 100%; }
.toolbar { display: flex; align-items: flex-end; justify-content: space-between; flex-wrap: wrap; gap: 14px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; }
.filter-btn {
  background: var(--glass); border: 1px solid var(--hairline); color: var(--muted);
  border-radius: 999px; padding: 6px 14px; font-size: 12px; cursor: pointer;
  transition: border-color .3s var(--ease-out), color .3s var(--ease-out), background .3s var(--ease-out);
}
.filter-btn:hover { border-color: rgba(167, 139, 250, .4); color: var(--text); }
.filter-btn.active { color: var(--text); border-color: rgba(167, 139, 250, .6); background: rgba(124, 77, 255, .18); }
.venue-filter {
  display: flex; flex-direction: column; gap: 6px; font-size: 11px; letter-spacing: .06em;
  text-transform: uppercase; color: var(--muted);
}
.venue-filter select {
  min-width: 220px; font: inherit; font-size: 14px; letter-spacing: 0; text-transform: none; color: var(--text);
  color-scheme: dark; background: rgba(255, 255, 255, .04); border: 1px solid var(--hairline);
  border-radius: 10px; padding: 8px 10px;
}
.hint, .empty-note { margin: 0; font-size: 13px; color: var(--muted); line-height: 1.6; }
.notice {
  margin: 0; font-size: 13px; color: #8EF0B5; background: rgba(142, 240, 181, .08);
  border: 1px solid rgba(142, 240, 181, .25); border-radius: 9px; padding: 11px 14px;
}

.booking-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.booking-card {
  display: flex; flex-direction: column; gap: 8px; background: var(--glass); border: 1px solid var(--hairline);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border-radius: 14px; padding: 18px 20px;
}
.card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.name-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-width: 0; }
.event-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 16px; line-height: 1.35; }
.venue { font-size: 14px; color: var(--text); }
.org { font-size: 13px; color: var(--body); }
.tag {
  font-size: 10px; letter-spacing: .06em; text-transform: uppercase; border-radius: 999px; padding: 2px 8px;
}
.competing { color: #FF8A76; background: rgba(255, 138, 118, .12); border: 1px solid rgba(255, 138, 118, .3); }
.held { color: #FFC66D; background: rgba(255, 198, 109, .1); border: 1px solid rgba(255, 198, 109, .3); }
.expired { color: var(--muted); background: rgba(255, 255, 255, .04); border: 1px solid var(--hairline); }
.status-pill {
  flex-shrink: 0; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--halo);
  background: rgba(124, 77, 255, .18); border: 1px solid rgba(167, 139, 250, .3); border-radius: 999px; padding: 3px 10px;
}

dl { margin: 4px 0 0; display: flex; flex-direction: column; gap: 6px; }
dl > div { display: grid; grid-template-columns: 120px 1fr; gap: 10px; }
dt { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding-top: 2px; }
dd { margin: 0; font-size: 13px; color: var(--body); line-height: 1.5; word-break: break-word; }

.approved p { margin: 0; font-size: 13px; line-height: 1.6; color: var(--body); }
.approved .locked { color: #8EF0B5; }
.approved .note { color: var(--muted); }
.actions { display: flex; gap: 10px; margin-top: auto; padding-top: 6px; }
.actions input {
  flex: 1; min-width: 0; font: inherit; font-size: 13px; color: var(--text); color-scheme: dark;
  background: rgba(255, 255, 255, .03); border: 1px solid var(--hairline); border-radius: 9px; padding: 8px 10px;
}
.btn:disabled { opacity: .55; cursor: progress; }
.row-error { margin: 0; font-size: 13px; color: #FF8A76; }
.form-error {
  color: #FF8A76; font-size: 13px; background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25); border-radius: 9px; padding: 11px 14px;
}

@media (max-width: 900px) {
  .booking-list { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  dl > div { grid-template-columns: 1fr; gap: 2px; }
}
</style>
