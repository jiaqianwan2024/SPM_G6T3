<template>
  <div class="request-check">
    <p v-if="loading" class="empty">Loading equipment requests…</p>
    <p v-else-if="error" class="empty error">{{ error }}</p>
    <p v-else-if="!groups.length" class="empty">No equipment requests yet.</p>
    <article v-for="group in groups" :key="group.eventId" class="event-card">
      <div class="event-header">
        <h3>Event {{ group.eventId }}</h3>
        <button type="button" class="btn btn-ghost small" data-testid="equipment-check" @click="check(group.eventId)">Check availability</button>
      </div>
      <p v-if="results[group.eventId]" class="verdict" :class="{ short: !results[group.eventId].canMeet }">
        {{ results[group.eventId].canMeet ? 'This request can be met.' : 'This request cannot be met.' }}
        Checking does not reserve anything.
      </p>
      <table v-if="results[group.eventId]" class="lines">
        <thead>
          <tr>
            <th>Equipment</th>
            <th>Requested</th>
            <th>Available</th>
            <th>Shortfall</th>
            <th>Held by</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(line, index) in results[group.eventId].lines" :key="`${line.equipmentId}-${index}`">
            <td>{{ line.name }}</td>
            <td>{{ line.requestedQuantity }}</td>
            <td>{{ line.availableQuantity }}</td>
            <td>{{ line.shortfall }}</td>
            <td>{{ heldBy(line) }}</td>
          </tr>
        </tbody>
      </table>
      <ul class="request-list">
        <li v-for="request in group.requests" :key="request.requestId" class="request-row">
          <div class="request-main">
            <strong>{{ request.quantity }} × {{ equipmentName(request.equipmentId) }}</strong>
            <span class="status">{{ statusLabel(request.status) }}</span>
          </div>
          <p v-if="request.technicalRequirements" class="notes">{{ request.technicalRequirements }}</p>
          <p v-if="request.reviewedBy" class="meta">
            Updated by {{ request.reviewedBy }}
            <template v-if="request.reviewedAt"> at {{ formatWhen(request.reviewedAt) }}</template>
          </p>
          <p v-if="request.reviewNote" class="notes">{{ request.reviewNote }}</p>
          <p v-if="request.status === 'partial'" class="notes" data-testid="equipment-shortfall">
            {{ request.reservedQuantity }} reserved, {{ request.shortfall }} short.
          </p>
          <p v-if="request.alternativeEquipmentId" class="notes">
            Suggested instead: {{ equipmentName(request.alternativeEquipmentId) }}
          </p>
          <p v-if="actionError[request.requestId]" class="error">{{ actionError[request.requestId] }}</p>
          <div v-if="request.status === 'pending' && decisionFor !== request.requestId" class="actions">
            <button type="button" class="btn btn-solid small" :disabled="busy === request.requestId" @click="accept(request)">Accept</button>
            <button type="button" class="btn btn-ghost small" :disabled="busy === request.requestId" @click="startDecision(request, 'reject')">Reject</button>
            <button type="button" class="btn btn-ghost small" :disabled="busy === request.requestId" @click="startDecision(request, 'unavailable')">Mark unavailable</button>
            <button type="button" class="btn btn-ghost small" data-testid="equipment-partial" :disabled="busy === request.requestId" @click="startDecision(request, 'partial')">Partly fulfil</button>
          </div>
          <div v-else-if="request.status === 'approved' && decisionFor !== request.requestId" class="actions">
            <button type="button" class="btn btn-solid small" data-testid="equipment-reserve" :disabled="busy === request.requestId" @click="reserve(request)">Reserve</button>
            <button type="button" class="btn btn-ghost small" data-testid="equipment-partial" :disabled="busy === request.requestId" @click="startDecision(request, 'partial')">Partly fulfil</button>
          </div>
          <!-- SPM-77 AC1 and AC2: unavailable with an optional alternative, or partly reserved with the shortfall. -->
          <form v-if="decisionFor === request.requestId" class="unavailable-form" @submit.prevent="confirmDecision(request)">
            <label v-if="decisionKind === 'partial'">
              <span>Units to reserve now (of {{ request.quantity }}) <span class="req">*</span></span>
              <input v-model.number="decisionQuantity" type="number" min="0" :max="request.quantity - 1" required data-testid="equipment-partial-quantity" />
            </label>
            <label><span>Reason <span class="req">*</span></span><input v-model="decisionReason" required /></label>
            <label v-if="decisionKind === 'unavailable'">Note<input v-model="decisionNote" /></label>
            <label v-if="decisionKind === 'unavailable'">
              Suggest an alternative (optional)
              <select v-model="decisionAlternative" data-testid="equipment-alternative">
                <option value="">No suggestion</option>
                <option v-for="option in alternatives(request)" :key="option.id" :value="option.id">{{ option.name }}</option>
              </select>
            </label>
            <div class="actions">
              <button type="button" class="btn btn-ghost small" @click="cancelDecision(request)">Cancel</button>
              <button type="submit" class="btn btn-solid small" :disabled="busy === request.requestId || !decisionReason.trim()">Save</button>
            </div>
          </form>
        </li>
      </ul>
      <!-- SPM-77 AC6: the whole request reviewed and complete marks the equipment arrangement ready. -->
      <div v-if="reviewable(group).length" class="actions group-actions">
        <button
          type="button"
          class="btn btn-ghost small"
          data-testid="equipment-complete-review"
          :disabled="busy === group.eventId"
          @click="completeReview(group)"
        >
          Mark review complete
        </button>
      </div>
      <!-- SPM-78 and SPM-86: what is held for the event, to change, release, or re-confirm. -->
      <section v-if="held(group.eventId).length" class="held" data-testid="equipment-reservations">
        <h4>Reservations</h4>
        <ul class="request-list">
          <li v-for="row in held(group.eventId)" :key="row.reservationId" class="request-row" :data-testid="`reservation-${row.reservationId}`">
            <div class="request-main">
              <strong>{{ row.quantity }} × {{ row.equipmentName || equipmentName(row.equipmentId) }}</strong>
              <span class="status">{{ row.status === 'partial' ? 'Partly reserved' : 'Reserved' }}</span>
            </div>
            <p v-if="row.needsReverification" class="notes flag" data-testid="reservation-reverify">
              Needs re-verification<template v-if="row.reverificationNote">: {{ row.reverificationNote }}</template>
            </p>
            <p v-if="actionError[row.reservationId]" class="error">{{ actionError[row.reservationId] }}</p>
            <div v-if="editingReservation !== row.reservationId" class="actions">
              <button v-if="row.needsReverification" type="button" class="btn btn-solid small" data-testid="reservation-reconfirm" :disabled="busy === row.reservationId" @click="reconfirm(row)">Re-confirm</button>
              <button type="button" class="btn btn-ghost small" data-testid="reservation-adjust" :disabled="busy === row.reservationId" @click="startReservation(row, 'adjust')">Change quantity</button>
              <button type="button" class="btn btn-ghost small" data-testid="reservation-release" :disabled="busy === row.reservationId" @click="startReservation(row, 'release')">Release</button>
            </div>
            <form v-else class="unavailable-form" @submit.prevent="saveReservation(row)">
              <label v-if="reservationKind === 'adjust'">
                <span>New quantity <span class="req">*</span></span>
                <input v-model.number="reservationQuantity" type="number" min="0" required data-testid="reservation-quantity" />
              </label>
              <label v-else>
                <span>Reason <span class="req">*</span><span class="req-note"> (needed once the event is confirmed)</span></span>
                <input v-model="reservationReason" data-testid="reservation-reason" />
              </label>
              <div class="actions">
                <button type="button" class="btn btn-ghost small" @click="editingReservation = ''">Cancel</button>
                <button type="submit" class="btn btn-solid small" :disabled="busy === row.reservationId" data-testid="reservation-save">
                  {{ reservationKind === 'adjust' ? 'Save quantity' : 'Release' }}
                </button>
              </div>
            </form>
          </li>
        </ul>
      </section>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  adjustEquipmentReservation,
  checkEquipmentAvailability,
  completeEquipmentReview,
  getEquipmentList,
  getEquipmentRequests,
  getEventReservations,
  markEquipmentRequestUnavailable,
  reconfirmEquipmentReservation,
  recordPartialFulfilment,
  releaseEquipmentReservation,
  reserveEquipmentRequest,
  reviewEquipmentRequest,
} from '../../api/equipmentService.js'
import { formatSgt, parseServerTime } from '../../utils/datetime.js'

// SPM-4 AC7: when set, only that event's requests are listed.
const props = defineProps({
  eventId: { type: String, default: '' },
})

const requests = ref([])
const names = ref({})
const results = ref({})
const loading = ref(true)
const error = ref('')
const actionError = ref({})
const busy = ref('')
const decisionFor = ref('')
const decisionKind = ref('')
const decisionReason = ref('')
const decisionNote = ref('')
const decisionQuantity = ref(0)
const decisionAlternative = ref('')
// Reservations held for each event, by event id.
const reservations = ref({})
const editingReservation = ref('')
const reservationKind = ref('')
const reservationQuantity = ref(0)
const reservationReason = ref('')
// Lines that are still being worked on; a complete, rejected or cancelled line needs no review.
const OPEN_LINES = ['pending', 'approved', 'reserved', 'partial', 'unavailable', 'attention', 'resolved']
const HELD = ['active', 'reserved', 'partial']

const groups = computed(() => {
  const grouped = new Map()
  for (const request of requests.value) {
    if (request.status === 'cancelled') continue
    if (props.eventId && request.eventId !== props.eventId) continue
    if (!grouped.has(request.eventId)) grouped.set(request.eventId, [])
    grouped.get(request.eventId).push(request)
  }
  return [...grouped.entries()].map(([eventId, rows]) => ({ eventId, requests: rows }))
})

function equipmentName(equipmentId) {
  return names.value[equipmentId] || equipmentId
}

function alternatives(request) {
  return Object.entries(names.value)
    .filter(([id]) => id !== request.equipmentId)
    .map(([id, name]) => ({ id, name }))
}

function held(eventId) {
  return (reservations.value[eventId] || []).filter((row) => HELD.includes(row.status))
}

function reviewable(group) {
  return group.requests.filter((request) => OPEN_LINES.includes(request.status))
}

function statusLabel(status) {
  if (status === 'pending') return 'Requested'
  if (status === 'approved') return 'Accepted'
  if (status === 'reserved') return 'Reserved'
  if (status === 'unavailable') return 'Unavailable'
  if (status === 'rejected') return 'Rejected'
  if (status === 'partial') return 'Partly reserved'
  if (status === 'resolved') return 'Shortfall accepted'
  if (status === 'complete') return 'Review complete'
  if (status === 'attention') return 'Needs attention'
  return status
}

function formatWhen(value) {
  return parseServerTime(value) ? formatSgt(value) : value
}

function heldBy(line) {
  const conflicts = line.conflictingEvents || []
  if (!conflicts.length) return '—'
  return conflicts.map((item) => `${item.eventId} (${item.quantity})`).join(', ')
}

function detail(err, fallback) {
  const message = err.response?.data?.detail
  return typeof message === 'string' ? message : fallback
}

async function loadReservations(eventIds) {
  const rows = await Promise.all(
    eventIds.map((eventId) => getEventReservations(eventId).then(({ data }) => [eventId, data]).catch(() => [eventId, []]))
  )
  reservations.value = { ...reservations.value, ...Object.fromEntries(rows) }
}

async function reload() {
  const { data } = await getEquipmentRequests()
  requests.value = data
  await loadReservations(groups.value.map((group) => group.eventId))
}

async function run(request, action) {
  busy.value = request.requestId
  actionError.value = { ...actionError.value, [request.requestId]: '' }
  try {
    await action()
    await reload()
  } catch (err) {
    actionError.value = { ...actionError.value, [request.requestId]: detail(err, 'This action could not be saved.') }
  } finally {
    busy.value = ''
  }
}

function accept(request) {
  return run(request, () => reviewEquipmentRequest(request.requestId, { approve: true, reviewNote: 'Accepted' }))
}

function reserve(request) {
  return run(request, () => reserveEquipmentRequest(request.requestId))
}

function startDecision(request, kind) {
  decisionFor.value = request.requestId
  decisionKind.value = kind
  decisionReason.value = ''
  decisionNote.value = ''
  decisionAlternative.value = ''
  decisionQuantity.value = Math.max(0, request.quantity - 1)
  actionError.value = { ...actionError.value, [request.requestId]: '' }
}

function cancelDecision(request) {
  decisionFor.value = ''
  decisionKind.value = ''
  decisionReason.value = ''
  decisionNote.value = ''
  actionError.value = { ...actionError.value, [request.requestId]: '' }
}

function confirmDecision(request) {
  const reason = decisionReason.value.trim()
  if (!reason) {
    actionError.value = { ...actionError.value, [request.requestId]: 'A reason is required.' }
    return
  }
  const note = decisionNote.value.trim()
  const kind = decisionKind.value
  return run(request, async () => {
    if (kind === 'reject') {
      await reviewEquipmentRequest(request.requestId, { approve: false, reviewNote: reason })
    } else if (kind === 'partial') {
      await recordPartialFulfilment(request.requestId, Number(decisionQuantity.value) || 0, reason)
    } else {
      await markEquipmentRequestUnavailable(request.requestId, {
        reason,
        note,
        alternativeEquipmentId: decisionAlternative.value || null,
      })
    }
    decisionFor.value = ''
  })
}

async function completeReview(group) {
  busy.value = group.eventId
  error.value = ''
  try {
    for (const request of reviewable(group)) await completeEquipmentReview(request.requestId)
    await reload()
  } catch (err) {
    error.value = detail(err, 'The review could not be marked complete.')
  } finally {
    busy.value = ''
  }
}

function startReservation(row, kind) {
  editingReservation.value = row.reservationId
  reservationKind.value = kind
  reservationQuantity.value = row.quantity
  reservationReason.value = ''
  actionError.value = { ...actionError.value, [row.reservationId]: '' }
}

async function runReservation(row, action) {
  busy.value = row.reservationId
  actionError.value = { ...actionError.value, [row.reservationId]: '' }
  try {
    await action()
    editingReservation.value = ''
    await reload()
  } catch (err) {
    actionError.value = { ...actionError.value, [row.reservationId]: detail(err, 'This change could not be saved.') }
  } finally {
    busy.value = ''
  }
}

function saveReservation(row) {
  if (reservationKind.value === 'adjust') {
    return runReservation(row, () => adjustEquipmentReservation(row.reservationId, Number(reservationQuantity.value) || 0))
  }
  return runReservation(row, () => releaseEquipmentReservation(row.reservationId, reservationReason.value.trim()))
}

function reconfirm(row) {
  return runReservation(row, () => reconfirmEquipmentReservation(row.reservationId))
}

async function check(eventId) {
  error.value = ''
  try {
    const { data } = await checkEquipmentAvailability({ eventId })
    results.value = { ...results.value, [eventId]: data }
  } catch {
    error.value = 'Unable to check that request. Please try again.'
  }
}

onMounted(async () => {
  try {
    const [requestList, equipmentList] = await Promise.all([getEquipmentRequests(), getEquipmentList()])
    requests.value = requestList.data
    names.value = Object.fromEntries(equipmentList.data.map((item) => [item.equipmentId, item.name]))
    await loadReservations(groups.value.map((group) => group.eventId))
  } catch {
    error.value = 'Unable to load equipment requests. Please try again.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.request-check { display: flex; flex-direction: column; gap: 14px; }
.event-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: 18px 20px;
}
.event-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
h3 { margin: 0; font-size: 16px; font-weight: 500; }
.verdict { margin: 12px 0 0; font-size: 14px; }
.verdict.short { color: #ffb4a8; }
.lines { width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px 8px 0; border-bottom: 1px solid var(--hairline); }
.request-list { list-style: none; margin: 14px 0 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.request-row { border-top: 1px solid var(--hairline); padding-top: 12px; }
.request-main { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.status { font-size: 12px; color: var(--muted); }
.notes, .meta { margin: 6px 0 0; font-size: 13px; color: var(--muted); }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.group-actions { justify-content: flex-end; }
.held { margin-top: 16px; }
.held h4 { margin: 0; font-size: 13px; font-weight: 500; color: var(--muted); letter-spacing: .04em; text-transform: uppercase; }
.flag { color: #ffd38a; }
.unavailable-form { display: grid; gap: 8px; margin-top: 10px; }
.unavailable-form label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.unavailable-form input,
.unavailable-form select {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  color: var(--text);
  font: inherit;
  font-size: 14px;
  padding: 8px 10px;
}
.empty { margin: 0; color: var(--muted); }
.error { color: #ffb4a8; font-size: 13px; }
</style>
