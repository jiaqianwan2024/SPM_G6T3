<template>
  <div class="attendee-home">
    <p v-if="loading" class="empty-note">Loading your events…</p>

    <template v-else>
      <!-- SPM-59: what the attendee is registered for, soonest first. -->
      <section class="block" data-testid="attendee-section-registrations">
        <h3>Your registrations</h3>
        <p v-if="registrationsError" class="form-error">{{ registrationsError }}</p>
        <div v-else-if="!registered.length" data-testid="attendee-registrations-empty">
          <p class="empty-note">You are not registered for any upcoming events. Browse events to find one.</p>
          <button type="button" class="btn btn-solid" data-testid="attendee-browse-events" @click="emit('open-tab', 'Browse Events')">
            Browse events
          </button>
        </div>
        <div v-else class="cards">
          <!-- AC1: the next upcoming registration is the first card, marked out from the rest. -->
          <button
            v-if="next"
            type="button"
            class="event-card next"
            data-testid="attendee-next-upcoming"
            :data-changed="next.changed ? 'true' : 'false'"
            :data-cancelled="'false'"
            @click="openRegistration(next)"
          >
            <span class="eyebrow">Next up</span>
            <span class="card-name" :title="next.eventName || next.eventId">{{ next.eventName || next.eventId }}</span>
            <span class="card-facts">
              <span class="fact"><span class="label">Date</span><span data-testid="attendee-next-upcoming-date">{{ datePart(startOf(next)) }}</span></span>
              <span class="fact"><span class="label">Time</span><span data-testid="attendee-next-upcoming-time">{{ timeRange(next) }}</span></span>
              <span class="fact">
                <span class="label">Venue</span>
                <span>
                  <span data-testid="attendee-next-upcoming-venue">{{ next.venueName || 'To be confirmed' }}</span>
                  <template v-if="next.venueLocation"> · </template>
                  <span data-testid="attendee-next-upcoming-location">{{ next.venueLocation }}</span>
                </span>
              </span>
            </span>
            <span v-if="changeFlags(next).length" class="flags">
              <span v-for="flag in changeFlags(next)" :key="flag" class="flag">{{ flag }}</span>
            </span>
          </button>

          <button
            v-for="row in others"
            :key="row.attendeeRegistrationId"
            type="button"
            class="event-card"
            :data-testid="`attendee-registration-${row.eventId}`"
            :data-changed="row.changed ? 'true' : 'false'"
            :data-cancelled="row.cancelled ? 'true' : 'false'"
            @click="openRegistration(row)"
          >
            <span class="card-name" :title="row.eventName || row.eventId">{{ row.eventName || row.eventId }}</span>
            <span class="card-facts">
              <span class="fact"><span class="label">Date</span><span>{{ datePart(startOf(row)) }}</span></span>
              <span class="fact"><span class="label">Time</span><span>{{ timeRange(row) }}</span></span>
              <span class="fact"><span class="label">Venue</span><span>{{ placeOf(row) }}</span></span>
            </span>
            <span v-if="row.cancelled" class="flags"><span class="flag cancelled">Cancelled</span></span>
            <span v-else-if="changeFlags(row).length" class="flags">
              <span v-for="flag in changeFlags(row)" :key="flag" class="flag">{{ flag }}</span>
            </span>
          </button>
        </div>
      </section>

      <!-- SPM-59 AC4: events open for registration, beneath the attendee's own. -->
      <section class="block" data-testid="attendee-section-open">
        <h3>Open for registration</h3>
        <p v-if="openError" class="form-error">{{ openError }}</p>
        <p v-else-if="!openEvents.length" class="empty-note" data-testid="attendee-open-empty">
          No other events are open for registration right now.
        </p>
        <div v-else class="cards">
          <button
            v-for="event in openEvents"
            :key="event.eventId"
            type="button"
            class="event-card"
            :data-testid="`attendee-open-${event.eventId}`"
            @click="router.push(`/app/browse/${event.eventId}`)"
          >
            <span class="card-name" :title="event.eventName">{{ event.eventName }}</span>
            <span class="card-facts">
              <span class="fact"><span class="label">Date</span><span>{{ datePart(startOf(event)) }}</span></span>
              <span class="fact"><span class="label">Time</span><span>{{ timeRange(event) }}</span></span>
              <span class="fact"><span class="label">Venue</span><span>{{ placeOf(event) }}</span></span>
            </span>
            <span class="places">{{ event.full ? 'Full' : `${event.remaining} place(s) remaining` }}</span>
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyRegistrations } from '../../api/registrationService.js'
import { getOpenEvents } from '../../api/eventService.js'
import { formatSgtDate, formatSgtTime, parseServerTime } from '../../utils/datetime.js'

const emit = defineEmits(['open-tab'])
const router = useRouter()

const loading = ref(true)
const registrations = ref([])
const openAll = ref([])
const registrationsError = ref('')
const openError = ref('')

const startOf = (row) => row.proposedStartAt || row.startsAt
const endOf = (row) => row.proposedEndAt || row.endsAt

function isPast(row) {
  const end = endOf(row) || startOf(row)
  return Boolean(end) && parseServerTime(end).getTime() < Date.now()
}

function byStart(a, b) {
  return (parseServerTime(startOf(a))?.getTime() || 0) - (parseServerTime(startOf(b))?.getTime() || 0)
}

// Withdrawn and finished registrations stay on My Registrations; the home shows what is still ahead.
const registered = computed(() =>
  registrations.value.filter((row) => row.status === 'registered' && !isPast(row)),
)
// AC1: the next upcoming registration first. A cancelled event is not upcoming, so those come after.
const ordered = computed(() => {
  const live = registered.value.filter((row) => !row.cancelled).sort(byStart)
  const cancelled = registered.value.filter((row) => row.cancelled).sort(byStart)
  return [...live, ...cancelled]
})
const next = computed(() => (ordered.value[0] && !ordered.value[0].cancelled ? ordered.value[0] : null))
const others = computed(() => (next.value ? ordered.value.slice(1) : ordered.value))

// An event the attendee is already registered for is listed above, not offered again.
const openEvents = computed(() => {
  const mine = new Set(registered.value.map((row) => row.eventId))
  return openAll.value.filter((event) => !mine.has(event.eventId)).sort(byStart)
})

// AC2: say what changed since they registered.
function changeFlags(row) {
  const flags = []
  if (row.dateChanged) flags.push('Date changed')
  if (row.timeChanged) flags.push('Time changed')
  if (row.venueChanged) flags.push('Venue changed')
  if (!flags.length && row.changed) flags.push('Changed')
  return flags
}

function datePart(value) {
  return value ? formatSgtDate(value) : 'To be confirmed'
}

function timePart(value) {
  return formatSgtTime(value)
}

function timeRange(row) {
  const start = timePart(startOf(row))
  const end = timePart(endOf(row))
  if (!start) return 'To be confirmed'
  return end ? `${start} – ${end} SGT` : `${start} SGT`
}

function placeOf(row) {
  return [row.venueName, row.venueLocation].filter(Boolean).join(' · ') || 'To be confirmed'
}

function openRegistration(row) {
  router.push(`/app/registrations/${row.attendeeRegistrationId}`)
}

function messageOf(err, fallback) {
  const detail = err.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

onMounted(async () => {
  const [mine, open] = await Promise.allSettled([getMyRegistrations(), getOpenEvents()])
  if (mine.status === 'fulfilled') registrations.value = mine.value.data
  else registrationsError.value = messageOf(mine.reason, 'Could not load your registrations.')
  if (open.status === 'fulfilled') openAll.value = open.value.data
  else openError.value = messageOf(open.reason, 'Could not load events open for registration.')
  loading.value = false
})
</script>

<style scoped>
.attendee-home { display: flex; flex-direction: column; gap: 28px; }
.block { display: flex; flex-direction: column; gap: 12px; }
.block h3 {
  margin: 0;
  font-family: var(--font);
  font-size: 15px;
  font-weight: 500;
  color: var(--text);
}
.empty-note { margin: 0 0 12px; font-size: 14px; color: var(--muted); }
.form-error {
  margin: 0;
  color: #FF8A76;
  font-size: 13px;
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
}
.event-card {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  text-align: left;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: 18px 20px;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.event-card:hover { border-color: rgba(167, 139, 250, .38); background: var(--glass-strong); }
.event-card:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.event-card.next {
  background: var(--glass-strong);
  border-color: rgba(167, 139, 250, .45);
}
.event-card.next:hover { border-color: rgba(167, 139, 250, .6); }
.event-card.next .eyebrow { margin-bottom: -6px; }
.eyebrow {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}
/* All registrations are cards, three to a row, with the next one first. */
.cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.card-name {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-lg);
  font-weight: 500;
  letter-spacing: -.01em;
  color: var(--text);
}
.card-facts { display: flex; flex-direction: column; gap: 6px; min-width: 0; max-width: 100%; }
.fact { display: flex; gap: 8px; font-size: 14px; line-height: 1.4; color: var(--body); }
.label { min-width: 52px; color: var(--muted); }
.flags { display: flex; flex-wrap: wrap; gap: 8px; }
.flag {
  font-size: 11px;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: #FFD59A;
}
.flag.cancelled { color: #FF8A76; }
.places { font-size: 13px; color: var(--muted); }

@media (max-width: 1100px) {
  .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 720px) {
  .cards { grid-template-columns: minmax(0, 1fr); }
}
</style>
