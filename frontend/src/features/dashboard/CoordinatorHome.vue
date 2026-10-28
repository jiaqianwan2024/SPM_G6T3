<template>
  <!-- The Event Coordinator's home: what needs them next. Built only on the reads
       their own screens use (Assigned Events, the event page's confirmation and
       change requests, the event's bookings and reservations), so every count
       and list follows the same access rules. Unassigned requests are the Lead's
       queue and never appear here. Each section fills in as its own reads return. -->
  <div class="coordinator-home" data-testid="coordinator-home">
    <div v-if="loading" class="loading">
      <UiSkeleton :lines="4" height="72px" />
    </div>
    <UiAlert v-else-if="error" tone="danger" data-testid="coordinator-home-error">{{ error }}</UiAlert>

    <template v-else>
      <div class="top">
        <StatGrid class="stats">
          <StatCard label="Your active events" :value="events.length" to="Assigned Events"
                    data-testid="coordinator-count-events" @open="$emit('open-tab', 'Assigned Events')" />
          <StatCard label="With outstanding arrangements" :value="gapsLoading ? '–' : withGaps.length"
                    data-testid="coordinator-count-outstanding" />
          <StatCard label="Change requests to decide" :value="changesLoading ? '–' : changeRequests.length"
                    data-testid="coordinator-count-changes" />
          <StatCard label="Flagged for re-verification" :value="flagsLoading ? '–' : flags.length"
                    data-testid="coordinator-count-reverify" />
        </StatGrid>
        <UiButton variant="outline" size="sm" data-testid="coordinator-home-refresh" @click="load">Refresh</UiButton>
      </div>

      <UiAlert v-if="partial" tone="warning" data-testid="coordinator-home-partial">
        Some details could not be loaded, so these lists may be incomplete. Refresh to try again.
      </UiAlert>

      <SectionBlock title="Flagged for re-verification" :count="flagsLoading ? null : flags.length"
                    data-testid="coordinator-section-reverify">
        <UiSkeleton v-if="flagsLoading" :lines="2" height="56px" />
        <UiEmptyState v-else-if="!flags.length" title="Nothing to re-verify"
                      hint="When a change puts a venue booking or equipment reservation in doubt, it shows up here first."
                      data-testid="coordinator-reverify-empty" />
        <template v-else>
          <UiAlert tone="warning" class="flag-banner">
            {{ flags.length === 1 ? '1 arrangement needs' : `${flags.length} arrangements need` }}
            re-verification. They do not count towards confirmation until they are re-confirmed.
          </UiAlert>
          <ul class="items">
            <li v-for="flag in flags" :key="flag.key">
              <RouterLink :to="eventLink(flag.event.eventId)" class="item attention"
                          :data-testid="`coordinator-reverify-${flag.key}`">
                <span class="item-top">
                  <span class="item-title">{{ flag.label }}</span>
                  <span class="kind">{{ flag.kind }}</span>
                </span>
                <span v-if="flag.note" class="item-body">{{ flag.note }}</span>
                <span class="item-meta">{{ eventName(flag.event) }} · {{ eventDateLabel(flag.event) }}</span>
              </RouterLink>
            </li>
          </ul>
        </template>
      </SectionBlock>

      <SectionBlock title="Change requests awaiting your decision" :count="changesLoading ? null : changeRequests.length"
                    data-testid="coordinator-section-changes">
        <UiSkeleton v-if="changesLoading" :lines="2" height="56px" />
        <UiEmptyState v-else-if="!changeRequests.length" title="No change requests to decide"
                      hint="When an organiser asks to change one of your events, it waits here for you."
                      data-testid="coordinator-changes-empty" />
        <ul v-else class="items">
          <li v-for="request in changeRequests" :key="request.changeRequestId">
            <RouterLink :to="eventLink(request.eventId)" class="item"
                        :data-testid="`coordinator-change-${request.changeRequestId}`">
              <span class="item-title">{{ request.reason }}</span>
              <span class="item-body">Proposes changing {{ proposedFields(request) }}</span>
              <span class="item-meta">
                {{ eventName(eventsById[request.eventId]) }} · raised {{ formatSgt(request.createdAt) }}
              </span>
            </RouterLink>
          </li>
        </ul>
      </SectionBlock>

      <SectionBlock title="Your events" :count="events.length" data-testid="coordinator-section-events">
        <UiEmptyState v-if="!events.length" title="No events are assigned to you"
                      hint="The Event Coordinator Lead assigns new requests. Until then they wait on the Lead's queue, not here."
                      data-testid="coordinator-events-empty" />
        <ul v-else class="items">
          <li v-for="event in events" :key="event.eventId">
            <RouterLink :to="eventLink(event.eventId)" class="item"
                        :class="{ attention: outstanding(event).length }"
                        :data-testid="`coordinator-event-${event.eventId}`">
              <span class="item-top">
                <span class="item-title">{{ eventName(event) }}</span>
                <StatusPill :status="event.status" :data-testid="`coordinator-event-${event.eventId}-status`" />
              </span>
              <span class="item-meta">
                {{ eventDateLabel(event) }} · {{ eventTimeLabel(event) }}
                <template v-if="event.organisationName"> · {{ event.organisationName }}</template>
              </span>
              <UiSkeleton v-if="gapsLoading && onPath(event)" />
              <span v-else-if="outstanding(event).length" class="outstanding"
                    :data-testid="`coordinator-event-${event.eventId}-outstanding`">
                <span class="label">Still outstanding</span>
                <span v-for="(gap, i) in outstanding(event)" :key="i" class="gap">
                  <span class="kind">{{ gap.kind }}</span>{{ gap.message }}
                </span>
              </span>
              <span v-else class="item-body" :data-testid="`coordinator-event-${event.eventId}-next`">
                {{ nextStep(event) }}
              </span>
            </RouterLink>
          </li>
        </ul>
      </SectionBlock>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getAssignedEvents, getChangeRequests, getConfirmation } from '../../api/eventService.js'
import { getVenueBookings } from '../../api/venueService.js'
import { getEventReservations } from '../../api/equipmentService.js'
import { CHANGE_REQUEST_STATUSES, CONFIRMATION_PATH_STATUSES } from '../../config/eventStatus.js'
import { fieldLabel } from '../../config/eventFields.js'
import { formatSgt, parseServerTime } from '../../utils/datetime.js'
import { eventDateLabel, eventTimeLabel } from '../../utils/eventSchedule.js'
import SectionBlock from '../../components/layout/SectionBlock.vue'
import StatCard from '../../components/layout/StatCard.vue'
import StatGrid from '../../components/layout/StatGrid.vue'
import StatusPill from '../../components/ui/StatusPill.vue'
import UiAlert from '../../components/ui/UiAlert.vue'
import UiButton from '../../components/ui/UiButton.vue'
import UiEmptyState from '../../components/ui/UiEmptyState.vue'
import UiSkeleton from '../../components/ui/UiSkeleton.vue'

defineEmits(['open-tab'])

// Finished events need nothing more from the coordinator (drafts never reach this list).
const CLOSED_STATUSES = ['completed', 'cancelled', 'rejected']
// From planning on, the event can hold venue bookings and equipment reservations.
const ARRANGED_STATUSES = [
  'approved', 'planning', 'safety review', 'safety approved', 'preparing', 'prepared', 'confirmed', 'reconsidering',
]
// The bookings and reservations that count towards the arrangement (as in event-service's arrangements.py).
const LIVE_BOOKINGS = ['pending', 'approved']
const HOLDING_RESERVATIONS = ['active', 'reserved']

const KIND_LABELS = { venue: 'Venue', equipment: 'Equipment', safety: 'Safety' }

const events = ref([])
const gapsByEvent = ref({}) // eventId -> [{ kind, message }]
const changeRequests = ref([])
const flags = ref([])
const loading = ref(true)
const gapsLoading = ref(true)
const changesLoading = ref(true)
const flagsLoading = ref(true)
const error = ref('')
const partial = ref(false)
// Each load gets a number, so a slow earlier load can't overwrite a refresh.
let currentLoad = 0

const eventsById = computed(() => Object.fromEntries(events.value.map((event) => [event.eventId, event])))
const withGaps = computed(() => events.value.filter((event) => outstanding(event).length))

const eventLink = (eventId) => `/app/events/${eventId}`
const eventName = (event) => event?.eventName || 'Untitled event'
// Events without a date sort last.
const startTime = (event) => parseServerTime(event.proposedStartAt)?.getTime() ?? 8.64e15
const onPath = (event) => CONFIRMATION_PATH_STATUSES.includes(event.status)

function outstanding(event) {
  return gapsByEvent.value[event.eventId] || []
}

function proposedFields(request) {
  const fields = Object.keys(request.proposedChanges || {}).map(fieldLabel)
  return fields.length ? fields.join(', ') : 'the event'
}

// What the event is waiting on when no arrangement is outstanding.
function nextStep(event) {
  switch (event.status) {
    case 'under review':
      return 'Review the request. Arrangements start once you approve it.'
    case 'changes requested':
      return 'Waiting for the organiser to answer your question.'
    case 'safety approved':
      return 'Everything is in place. Confirm the event.'
    case 'reconsidering':
      return 'Arrangements are being re-checked after a change.'
    case 'confirmed': {
      const end = parseServerTime(event.proposedEndAt)
      return end && end < new Date() ? 'It has taken place. Mark it completed.' : 'All arrangements confirmed.'
    }
    default:
      return 'Nothing outstanding.'
  }
}

const fulfilled = (results) => results.filter((result) => result.status === 'fulfilled').map((result) => result.value.data)

// The event page's confirmation check. The event's stage is already shown by its
// status pill, so only arrangement gaps are listed.
async function loadGaps(mine, run) {
  const path = mine.filter(onPath)
  const results = await Promise.allSettled(path.map((event) => getConfirmation(event.eventId)))
  if (run !== currentLoad) return
  const gaps = {}
  results.forEach((result, i) => {
    if (result.status !== 'fulfilled') return
    const list = result.value.data.missing.filter((gap) => gap.kind !== 'status')
    if (list.length) gaps[path[i].eventId] = list.map((gap) => ({ ...gap, kind: KIND_LABELS[gap.kind] }))
  })
  gapsByEvent.value = gaps
  partial.value ||= results.length !== fulfilled(results).length
  gapsLoading.value = false
}

async function loadChanges(mine, run) {
  const changeable = mine.filter((event) => CHANGE_REQUEST_STATUSES.includes(event.status))
  const results = await Promise.allSettled(changeable.map((event) => getChangeRequests(event.eventId)))
  if (run !== currentLoad) return
  changeRequests.value = fulfilled(results)
    .flat()
    .filter((request) => request.status === 'pending')
    .sort((a, b) => parseServerTime(b.createdAt) - parseServerTime(a.createdAt))
  partial.value ||= results.length !== fulfilled(results).length
  changesLoading.value = false
}

async function loadFlags(mine, run) {
  const arranged = mine.filter((event) => ARRANGED_STATUSES.includes(event.status))
  const byId = Object.fromEntries(arranged.map((event) => [event.eventId, event]))
  const [bookings, reservations] = await Promise.all([
    arranged.length ? getVenueBookings().then((r) => r.data).catch(() => null) : [],
    Promise.allSettled(arranged.map((event) => getEventReservations(event.eventId))),
  ])
  if (run !== currentLoad) return
  const venueFlags = (bookings || [])
    .filter((row) => byId[row.eventId] && row.needsReverification && LIVE_BOOKINGS.includes(row.status))
    .map((row) => ({
      key: `booking-${row.bookingId}`,
      kind: 'Venue',
      label: row.venueName || row.venueId,
      note: row.reverificationNote,
      event: byId[row.eventId],
    }))
  const equipmentFlags = fulfilled(reservations)
    .flat()
    .filter((row) => byId[row.eventId] && row.needsReverification && HOLDING_RESERVATIONS.includes(row.status))
    .map((row) => ({
      key: `reservation-${row.reservationId}`,
      kind: 'Equipment',
      label: `${row.quantity} × ${row.equipmentName || row.equipmentId}`,
      note: row.reverificationNote,
      event: byId[row.eventId],
    }))
  flags.value = [...venueFlags, ...equipmentFlags].sort((a, b) => startTime(a.event) - startTime(b.event))
  partial.value ||= bookings === null || reservations.length !== fulfilled(reservations).length
  flagsLoading.value = false
}

// The events list shows as soon as it arrives; each section then fills in on its
// own, so one slow or refused event doesn't hold up or blank the home screen.
async function load() {
  const run = ++currentLoad
  error.value = ''
  partial.value = false
  gapsLoading.value = changesLoading.value = flagsLoading.value = true
  try {
    const { data } = await getAssignedEvents()
    if (run !== currentLoad) return
    const mine = data
      .filter((event) => !CLOSED_STATUSES.includes(event.status))
      .sort((a, b) => startTime(a) - startTime(b))
    events.value = mine
    loading.value = false
    loadGaps(mine, run)
    loadChanges(mine, run)
    loadFlags(mine, run)
  } catch (err) {
    if (run !== currentLoad) return
    error.value = err.response?.data?.detail || 'Could not load your home screen. Please try again.'
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.coordinator-home { display: flex; flex-direction: column; gap: var(--space-5); }

.top { display: flex; align-items: flex-start; gap: var(--space-5); flex-wrap: wrap; }
.stats { flex: 1 1 520px; }

.flag-banner { margin-bottom: var(--space-3); }

.items { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  color: var(--body);
  text-decoration: none;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  transition: border-color .3s var(--ease-out), background .3s var(--ease-out);
}
.item:hover { border-color: rgba(167, 139, 250, .4); background: var(--glass-strong); }
.item:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.item.attention { border-color: rgba(245, 196, 81, .45); }
.item-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.item-title { color: var(--text); font-size: var(--fs-md); font-weight: 500; }
.item-body { font-size: var(--fs-sm); }
.item-meta { font-size: var(--fs-xs); color: var(--muted); }

.outstanding { display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--fs-sm); }
.label { font-size: var(--fs-xs); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.gap { display: flex; align-items: baseline; gap: var(--space-2); }
.kind {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: var(--radius-pill);
  border: 1px solid rgba(245, 196, 81, .4);
  color: var(--warning);
  font-size: var(--fs-xs);
}
</style>
