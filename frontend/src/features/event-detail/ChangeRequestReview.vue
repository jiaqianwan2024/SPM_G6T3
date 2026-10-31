<template>
  <!-- SPM-85: the assigned coordinator reviews a change request and its impact before deciding. -->
  <div class="review-page">
    <button type="button" class="btn btn-ghost back" @click="goBack">← Event details</button>

    <p v-if="loading" class="empty-note">Loading the change request…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <template v-else>
      <header class="page-head">
        <p class="eyebrow">Change request</p>
        <h1>{{ event.eventName }}</h1>
      </header>

      <!-- AC1: each field's current and proposed value, and the organiser's reason. -->
      <section class="panel" data-testid="change-request-review">
        <div class="panel-head">
          <h2>What the organiser asked for</h2>
          <span class="state" :class="request.status" data-testid="change-request-status">{{ request.status }}</span>
        </div>
        <p class="meta">Requested {{ formatSgt(request.createdAt) }}</p>
        <table class="changes">
          <thead>
            <tr><th>Field</th><th>Current</th><th>Proposed</th></tr>
          </thead>
          <tbody>
            <tr v-for="(value, field) in request.proposedChanges" :key="field">
              <td>{{ fieldLabel(field) }}</td>
              <td data-testid="change-current">{{ formatValue(field, request.currentValues?.[field] ?? event[field]) }}</td>
              <td class="proposed" data-testid="change-proposed">{{ formatValue(field, value) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="reason"><span>Reason</span>{{ request.reason }}</p>

        <p v-if="request.status !== 'pending'" class="outcome" :class="request.status" data-testid="change-request-review-outcome">
          <strong>{{ request.status }}</strong> {{ formatSgt(request.reviewedAt) }}<template v-if="request.decisionReason"
            >. Reason: {{ request.decisionReason }}</template><template v-if="request.narrowerRequested"
            >. A narrower request was asked for.</template>
        </p>
      </section>

      <!-- AC2 to AC5: what accepting would affect, before deciding. -->
      <section v-if="canDecide" class="panel" data-testid="change-request-impact">
        <h2>Impact if accepted</h2>
        <p v-if="impactLoading" class="empty-note">Checking venue, equipment and registrations…</p>
        <p v-else-if="impactError" class="form-error">{{ impactError }}</p>
        <template v-else-if="impact">
          <div v-if="impact.unchecked.length" class="warning" data-testid="impact-unchecked">
            {{ uncheckedText }} could not be checked right now. Check again before accepting.
          </div>
          <p v-if="nothingAffected" class="empty-note" data-testid="impact-none">
            This change does not affect any venue booking, equipment reservation or registration.
          </p>

          <div v-if="showVenue" class="impact-part" data-testid="impact-venue">
            <h3>Venue bookings</h3>
            <p v-if="!impact.venueBookings.length" class="empty-note">No confirmed venue booking.</p>
            <ul v-else class="items">
              <li v-for="booking in impact.venueBookings" :key="booking.bookingId">
                <strong>{{ booking.venueName }}</strong> · {{ formatSgtRange(booking.startsAt, booking.endsAt) }}
              </li>
            </ul>
            <!-- AC3: the suitability check re-run at the proposed date, time and layout. -->
            <div
              v-for="row in impact.venueSuitability || []"
              :key="`suit-${row.bookingId}`"
              class="finding"
              :class="verdictClass(row.verdict)"
              data-testid="impact-suitability"
            >
              <p><strong>{{ row.venueName }}</strong> is {{ row.verdict }} at the proposed values.</p>
              <ul v-if="row.reasons.length"><li v-for="reason in row.reasons" :key="reason">{{ reason }}</li></ul>
            </div>
            <!-- AC4: attendance against the booked venue's capacity in the layout. -->
            <p
              v-for="row in impact.capacity || []"
              :key="`cap-${row.bookingId}`"
              class="finding"
              :class="row.overCapacity ? 'bad' : 'good'"
              data-testid="impact-capacity"
            >
              {{ capacityText(row) }}
            </p>
          </div>

          <div v-if="showEquipment" class="impact-part" data-testid="impact-equipment">
            <h3>Equipment</h3>
            <p v-if="!impact.equipmentReservations.length" class="empty-note">No equipment reservation is affected.</p>
            <ul v-else class="items">
              <li v-for="row in impact.equipmentReservations" :key="row.reservationId">
                Reservation: {{ row.quantity }} × {{ row.equipmentName }}
              </li>
            </ul>
            <!-- AC5: whether a raised quantity can be had for the event's period. -->
            <p
              v-for="row in impact.equipmentAvailability || []"
              :key="`eq-${row.equipmentId}`"
              class="finding"
              :class="row.available ? 'good' : 'bad'"
              data-testid="impact-equipment-availability"
            >
              {{ equipmentText(row) }}
            </p>
          </div>

          <div v-if="showRegistrations" class="impact-part" data-testid="impact-registrations">
            <h3>Registrations</h3>
            <p v-if="!impact.registrations.length" class="empty-note">Nobody is registered yet.</p>
            <template v-else>
              <p class="meta">{{ impact.registrations.length }} registered {{ impact.registrations.length === 1 ? 'attendee' : 'attendees' }}</p>
              <ul class="items">
                <li v-for="row in impact.registrations" :key="row.attendeeEmail">{{ row.attendeeName }} · {{ row.attendeeEmail }}</li>
              </ul>
            </template>
          </div>
        </template>
      </section>

      <section v-if="canDecide" class="panel">
        <h2>Decision</h2>
        <ChangeRequestDecision :event-id="event.eventId" :change-request-id="request.changeRequestId" @decided="load" />
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEquipmentList } from '../../api/equipmentService.js'
import { getChangeRequestImpact, getChangeRequests, getEvent } from '../../api/eventService.js'
import { fieldLabel } from '../../config/eventFields.js'
import { session } from '../../store/session.js'
import { formatSgt, formatSgtRange } from '../../utils/datetime.js'
import ChangeRequestDecision from './ChangeRequestDecision.vue'
import { errorText, formatChangeValue } from './changeRequestValues.js'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const event = ref(null)
const request = ref(null)
const names = ref({})
const impact = ref(null)
const impactLoading = ref(false)
const impactError = ref('')

const canDecide = computed(
  () =>
    request.value?.status === 'pending' &&
    session.role === 'coordinator' &&
    !!event.value?.coordinatorId &&
    event.value.coordinatorId === session.userId,
)
const showVenue = computed(() => !!impact.value && (request.value.affectsVenue || impact.value.venueBookings.length > 0))
const showEquipment = computed(
  () => !!impact.value && (request.value.affectsEquipment || impact.value.equipmentReservations.length > 0),
)
const showRegistrations = computed(
  () => !!impact.value && (request.value.affectsRegistration || impact.value.registrations.length > 0),
)
const nothingAffected = computed(
  () => !showVenue.value && !showEquipment.value && !showRegistrations.value && !impact.value.unchecked.length,
)
const UNCHECKED_LABELS = { venue: 'Venue bookings', equipment: 'Equipment', registrations: 'Registrations' }
const uncheckedText = computed(() => impact.value.unchecked.map((part) => UNCHECKED_LABELS[part] || part).join(', '))

const formatValue = (field, value) => formatChangeValue(field, value, names.value)

function verdictClass(verdict) {
  if (verdict === 'suitable') return 'good'
  return verdict === 'not suitable' ? 'bad' : 'warn'
}

function capacityText(row) {
  const layout = row.layout ? `the ${row.layout} layout` : 'its largest layout'
  if (row.overCapacity) {
    return `Expected attendance of ${row.expectedAttendance} is above ${row.venueName}'s capacity of ${row.capacity} in ${layout}.`
  }
  return `${row.venueName} holds ${row.capacity} in ${layout}, enough for the expected ${row.expectedAttendance}.`
}

function equipmentText(row) {
  const change = `${row.equipmentName}: ${row.currentQuantity} → ${row.proposedQuantity} (${row.extraQuantity} more).`
  const stock = `${row.freeQuantity} free for the event's period and ${row.heldQuantity} already reserved for it`
  return row.available ? `${change} ${stock}, so it can be met.` : `${change} ${stock}, so ${row.shortfall} short.`
}

function goBack() {
  router.push(`/app/events/${route.params.id}`)
}

async function loadImpact() {
  impact.value = null
  if (!canDecide.value) return
  impactLoading.value = true
  impactError.value = ''
  try {
    const { data } = await getChangeRequestImpact(route.params.id, route.params.changeRequestId)
    impact.value = data
  } catch (err) {
    impactError.value = errorText(err, 'Could not assess the change. Please try again.')
  } finally {
    impactLoading.value = false
  }
}

async function load() {
  error.value = ''
  try {
    const [eventResult, requestsResult] = await Promise.all([
      getEvent(route.params.id),
      getChangeRequests(route.params.id),
    ])
    event.value = eventResult.data
    request.value = requestsResult.data.find((row) => row.changeRequestId === route.params.changeRequestId) || null
    if (!request.value) error.value = 'This change request was not found on the event.'
  } catch (err) {
    error.value = errorText(err, 'Could not load the change request. Please try again.')
  } finally {
    loading.value = false
  }
  await loadImpact()
}

async function loadNames() {
  try {
    const { data } = await getEquipmentList()
    names.value = Object.fromEntries((data || []).map((item) => [item.equipmentId, item.name]))
  } catch {
    names.value = {}
  }
}

onMounted(() => Promise.all([load(), loadNames()]))
</script>

<style scoped>
.review-page { padding: 28px 0 48px; }
.back { margin: 0 0 18px; }

.page-head { margin-bottom: 22px; }
.eyebrow { margin: 0; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.page-head h1 { margin: 6px 0 0; font-size: 28px; font-weight: 500; letter-spacing: -.02em; }

.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: var(--radius);
  padding: 22px 24px;
  margin-bottom: 18px;
}
.panel h2 { margin: 0 0 12px; font-size: 16px; font-weight: 500; }
.panel-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.panel-head h2 { margin-bottom: 4px; }
.meta { font-size: 12px; color: var(--muted); margin: 0 0 12px; }
.empty-note { font-size: 14px; color: var(--muted); margin: 0 0 8px; }

.state { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; border-radius: var(--radius-pill); padding: 2px 9px; border: 1px solid var(--hairline); color: var(--body); }
.state.pending { color: #FFD9A8; background: rgba(255, 170, 80, .1); border-color: rgba(255, 196, 120, .35); }
.state.declined { color: #FF8A76; border-color: rgba(255, 138, 118, .35); }
.state.accepted { color: var(--halo); border-color: rgba(167, 139, 250, .35); }

.changes { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 10px; table-layout: fixed; }
.changes th { text-align: left; font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 400; padding: 4px 8px 6px 0; }
.changes td { padding: 6px 8px 6px 0; border-top: 1px solid var(--hairline); color: var(--body); vertical-align: top; word-break: break-word; }
.changes td.proposed { color: var(--text); }
.reason { font-size: 13px; color: var(--body); margin: 0; line-height: 1.5; }
.reason span { font-size: 10px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin-right: 8px; }
.outcome { font-size: 13px; line-height: 1.6; color: var(--body); margin: 12px 0 0; text-transform: none; }
.outcome strong { text-transform: capitalize; }
.outcome.declined strong { color: #FF8A76; }
.outcome.accepted strong { color: var(--halo); }

.impact-part { border-top: 1px solid var(--hairline); padding-top: 12px; margin-top: 12px; }
.impact-part h3 { margin: 0 0 8px; font-size: 13px; font-weight: 500; color: var(--text); }
.items { margin: 0 0 8px; padding-left: 18px; font-size: 13px; line-height: 1.7; color: var(--body); }
.finding { font-size: 13px; line-height: 1.6; border-radius: var(--radius); padding: 8px 12px; margin: 0 0 8px; border: 1px solid var(--hairline); color: var(--body); }
.finding p, .finding ul { margin: 0; }
.finding ul { padding-left: 18px; }
.finding.good { border-color: rgba(167, 139, 250, .3); }
.finding.warn { color: #FFD9A8; border-color: rgba(255, 196, 120, .3); background: rgba(255, 170, 80, .06); }
.finding.bad { color: #FF8A76; border-color: rgba(255, 138, 118, .3); background: rgba(255, 138, 118, .06); }
.warning {
  font-size: 13px;
  line-height: 1.6;
  color: #FFD9A8;
  background: rgba(255, 170, 80, .08);
  border: 1px solid rgba(255, 196, 120, .3);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin-bottom: 12px;
}
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
  margin: 8px 0 0;
}

@media (max-width: 560px) {
  .panel { padding: 18px 16px; }
  .changes { table-layout: auto; }
}
</style>
