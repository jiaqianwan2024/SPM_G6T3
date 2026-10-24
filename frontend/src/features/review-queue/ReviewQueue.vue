<template>
  <div class="review-queue">
    <!-- While a dialog floats above (assign, approve, or reject), the queue and
         the details popup behind it are inert — otherwise their own "Assign" /
         "Approve" / "Reject" buttons stay in the accessibility tree alongside the
         dialog's, so a role-based lookup for either matches two elements. -->
    <div :inert="dialogOpen || null" :aria-hidden="dialogOpen ? 'true' : null">
    <div v-if="!loading && !error" class="queue-toolbar">
      <label class="search">
        Search
        <input v-model="query" type="search" placeholder="Event or organisation" />
      </label>
      <div class="queue-filters">
        <button
          v-if="isLead"
          class="filter-btn"
          :class="{ active: filter === 'unassigned' }"
          data-testid="queue-filter-unassigned"
          @click="toggleFilter('unassigned')"
        >
          Unassigned only
        </button>
        <label class="include-completed">
          <input
            v-model="includeCompleted"
            type="checkbox"
            data-testid="queue-include-completed"
            @change="loadEvents"
          />
          Include completed events
        </label>
        <button
          class="filter-btn"
          :class="{ active: sortMode === 'name-asc' }"
          @click="setSort('name-asc')"
        >
          A–Z
        </button>
        <button
          class="filter-btn"
          :class="{ active: sortMode === 'name-desc' }"
          @click="setSort('name-desc')"
        >
          Z–A
        </button>
      </div>
    </div>

    <p v-if="loading" class="empty-note">Loading submitted events…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!filteredEvents.length" data-testid="review-queue-empty" class="empty-note">
      {{ emptyMessage }}
    </p>

    <div v-else class="event-list">
      <div
        v-for="event in filteredEvents"
        :key="event.eventId"
        class="event-card"
        :data-testid="`review-queue-${event.eventId}`"
        :data-assigned="String(!!event.coordinatorId)"
        role="button"
        tabindex="0"
        @click="openDetails(event)"
        @keydown.enter="openDetails(event)"
      >
        <div class="event-top">
          <div class="event-name-row">
            <span class="event-name">{{ event.eventName }}</span>
            <span v-if="event.dateNear" class="near-flag">Date is near</span>
          </div>
          <span data-testid="queue-status" class="status-pill">{{ event.status }}</span>
        </div>
        <div v-if="event.organisationName" class="event-org">{{ event.organisationName }}</div>
        <div class="event-when" data-testid="queue-datetime">
          {{ formatSgtRange(event.proposedStartAt, event.proposedEndAt) }}
        </div>
        <div class="event-wait" data-testid="queue-submitted-at">
          Submitted {{ formatSubmitted(event.submittedAt) }} · waiting {{ waitingFor(event.submittedAt) }}
        </div>
        <div class="event-facts">
          <span data-testid="queue-attendance">{{ event.expectedAttendance }} attendees</span>
          <span v-if="isLead" class="event-assignee" data-testid="queue-assignee">{{ assigneeLabel(event) }}</span>
        </div>
        <div class="actions">
          <button
            v-if="canApprove(event)"
            class="btn btn-solid"
            :disabled="isBusy(event.eventId)"
            @click.stop="approving = event"
          >
            Approve
          </button>
          <button
            v-if="canReject(event)"
            class="btn btn-outline"
            :disabled="isBusy(event.eventId)"
            @click.stop="openReject(event)"
          >
            Reject
          </button>
        </div>
        <p v-if="rowErrors[event.eventId]" class="row-error">{{ rowErrors[event.eventId] }}</p>
      </div>
    </div>

    <!-- Event details popup -->
    <div v-if="selected" class="modal-backdrop" @click.self="closeDetails">
      <div class="modal details-modal" role="dialog" aria-modal="true">
        <div class="details-head">
          <div>
            <h3>{{ selected.eventName }}</h3>
            <span class="status-pill">{{ selected.status }}</span>
          </div>
          <button class="close-btn" aria-label="Close" @click="closeDetails">×</button>
        </div>

        <div class="details-body">
          <dl>
            <div v-for="row in detailRows(selected)" :key="row.label" class="detail-row" :class="{ wide: row.wide }">
              <dt>{{ row.label }}</dt>
              <dd :class="{ empty: row.empty }">{{ row.value }}</dd>
            </div>
          </dl>
        </div>

        <p v-if="rowErrors[selected.eventId]" class="row-error">{{ rowErrors[selected.eventId] }}</p>

        <div class="details-actions">
          <button
            v-if="isLead"
            class="btn btn-outline"
            :disabled="isBusy(selected.eventId)"
            data-testid="queue-assign-coordinator"
            @click="assigning = selected"
          >
            {{ selected.coordinatorId ? 'Reassign coordinator' : 'Assign coordinator' }}
          </button>
          <button
            v-if="canReject(selected)"
            class="btn btn-outline"
            :disabled="isBusy(selected.eventId)"
            @click="openReject(selected)"
          >
            Reject
          </button>
          <button
            v-if="canApprove(selected)"
            class="btn btn-solid"
            :disabled="isBusy(selected.eventId)"
            @click="approving = selected"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
    </div>

    <!-- The Event Coordinator Lead assigns from the queue (stacks above the details popup) -->
    <AssignCoordinatorDialog
      v-if="assigning"
      :event="assigning"
      @close="assigning = null"
      @assigned="onAssigned"
    />

    <!-- SPM-69: approve with an optional note (stacks above the details popup) -->
    <ApproveEventDialog
      v-if="approving"
      :event="approving"
      @close="approving = null"
      @approved="onApproved"
    />

    <!-- Reject reason modal (stacks above the details popup when opened from it) -->
    <div v-if="rejecting" class="modal-backdrop" @click.self="rejecting = null">
      <div class="modal">
        <h3>Reject {{ rejecting.eventName }}</h3>
        <label for="reject-reason">Reason</label>
        <select id="reject-reason" v-model="rejectReason" data-testid="reject-reason">
          <option value="" disabled>Choose a reason</option>
          <option v-for="reason in REJECTION_REASONS" :key="reason" :value="reason">{{ reason }}</option>
        </select>
        <label for="reject-explanation">Explanation for the organiser</label>
        <textarea
          id="reject-explanation"
          v-model="rejectExplanation"
          rows="3"
          maxlength="2000"
          placeholder="Let the organiser know why"
          data-testid="reject-explanation"
        ></textarea>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="rejecting = null">Cancel</button>
          <button
            class="btn btn-solid"
            data-testid="reject-confirm"
            :disabled="isBusy(rejecting.eventId) || !rejectReason || !rejectExplanation.trim()"
            @click="confirmReject"
          >
            Reject event
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { getCoordinatorCandidates, getSubmissionQueue, rejectEvent } from '../../api/eventService.js'
import { getMe } from '../../api/userService.js'
import { IN_REVIEW_EVENT_STATUSES, REJECTION_REASONS } from '../../config/eventStatus.js'
import { session } from '../../store/session.js'
import ApproveEventDialog from '../event-detail/ApproveEventDialog.vue'
import AssignCoordinatorDialog from '../event-detail/AssignCoordinatorDialog.vue'
import { formatSgt, formatSgtRange } from '../../utils/datetime.js'

const events = ref([])
const loading = ref(true)
const error = ref('')
const busyIds = reactive(new Set())
const rowErrors = reactive({})

const selected = ref(null)
const rejecting = ref(null)
const rejectReason = ref('')
const rejectExplanation = ref('')
const assigning = ref(null)
const approving = ref(null)
const dialogOpen = computed(() => Boolean(assigning.value || rejecting.value || approving.value))

// 'all' | 'unassigned' (the Lead's filter)
const filter = ref('all')
// The Event Coordinator Lead sees every request and assigns them; a coordinator
// sees only the requests assigned to them (the server applies the same rule).
const isLead = computed(() => session.role === 'coordinatorlead')
// userId -> name, so the Lead sees who each request is with. Display only.
const coordinatorNames = ref({})
const query = ref('')
// SPM-73 AC5: completed events are left out of the queue unless asked for.
const includeCompleted = ref(false)
// 'waiting' keeps the server order (longest-waiting first).
const sortMode = ref('waiting')
const myUserId = ref(null)

// Ticks once a minute so the "waiting" times stay current without a reload.
const now = ref(Date.now())
let ticker = null

function isBusy(eventId) {
  return busyIds.has(eventId)
}

// SPM-69 AC1/AC5: only the assigned coordinator approves, so an unassigned
// request offers no Approve at all. The server enforces the same.
function canApprove(event) {
  return (
    !!event.coordinatorId &&
    event.coordinatorId === myUserId.value &&
    IN_REVIEW_EVENT_STATUSES.includes(event.status)
  )
}

// SPM-70 AC1: only the assigned coordinator rejects, while the request is under review or has changes requested.
function canReject(event) {
  return !!event.coordinatorId && event.coordinatorId === myUserId.value && IN_REVIEW_EVENT_STATUSES.includes(event.status)
}

function coordinatorName(userId) {
  return coordinatorNames.value[userId] || userId
}

function assigneeLabel(event) {
  return event.coordinatorId ? `Assigned to ${coordinatorName(event.coordinatorId)}` : 'Unassigned'
}

// The server sends UTC without a zone marker, and new Date() reads a
// marker-less string as *local* time, so read it as UTC. Every time is shown
// in Singapore time.
function parseUtc(value) {
  if (!value) return null
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

function waitingFor(submittedAt) {
  const start = parseUtc(submittedAt)
  if (!start) return 'unknown'
  const minutes = Math.max(0, Math.floor((now.value - start.getTime()) / 60000))
  if (minutes < 1) return 'under a minute'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ${minutes % 60}m`
  const days = Math.floor(hours / 24)
  return `${days}d ${hours % 24}h`
}

function formatSubmitted(value) {
  return formatSgt(value)
}

const filteredEvents = computed(() => {
  let list = events.value
  if (filter.value === 'unassigned') list = list.filter((event) => !event.coordinatorId)
  const term = query.value.trim().toLowerCase()
  if (term) {
    list = list.filter((event) => {
      const name = (event.eventName || '').toLowerCase()
      const organisation = (event.organisationName || '').toLowerCase()
      return name.includes(term) || organisation.includes(term)
    })
  }
  if (sortMode.value === 'name-asc' || sortMode.value === 'name-desc') {
    const direction = sortMode.value === 'name-asc' ? 1 : -1
    list = [...list].sort(
      (a, b) =>
        direction *
        String(a.eventName || '').localeCompare(String(b.eventName || ''), undefined, { sensitivity: 'base' }),
    )
  }
  return list
})

const emptyMessage = computed(() => {
  if (query.value.trim()) return 'No requests match this search.'
  if (filter.value === 'unassigned') return 'No unassigned requests match this filter.'
  if (!isLead.value) return 'No requests are currently assigned to you.'
  return 'No requests are awaiting review.'
})

function toggleFilter(mode) {
  filter.value = filter.value === mode ? 'all' : mode
}

function setSort(mode) {
  sortMode.value = sortMode.value === mode ? 'waiting' : mode
}

function detailRows(event) {
  const wideLabels = new Set([
    'Purpose',
    'Description',
    'Venue requirements',
    'Equipment requirements',
    'Accessibility needs',
  ])
  const rows = [
    { label: 'Organisation', value: event.organisationName },
    { label: 'Submitted', value: formatSubmitted(event.submittedAt) },
    { label: 'Waiting', value: waitingFor(event.submittedAt) },
    { label: 'Assigned coordinator', value: event.coordinatorId ? coordinatorName(event.coordinatorId) : '' },
    { label: 'Category', value: event.category },
    { label: 'Proposed start', value: formatSgt(event.proposedStartAt) },
    { label: 'Proposed end', value: formatSgt(event.proposedEndAt) },
    { label: 'Expected attendance', value: event.expectedAttendance != null ? String(event.expectedAttendance) : '' },
    { label: 'Purpose', value: event.purpose },
    { label: 'Description', value: event.description },
    { label: 'Venue requirements', value: event.venueRequirements },
    { label: 'Equipment requirements', value: event.equipmentRequirements },
    { label: 'Accessibility needs', value: event.accessibilityNeeds },
    { label: 'Layout preference', value: event.layoutPreference },
    { label: 'Registration', value: event.registrationEnabled ? 'Enabled' : 'Not enabled' },
  ].map((row) => ({ ...row, wide: wideLabels.has(row.label) }))
  if (event.registrationEnabled) {
    rows.push(
      { label: 'Registration opens', value: formatSgt(event.registrationOpensAt) },
      { label: 'Registration closes', value: formatSgt(event.registrationClosesAt) },
      { label: 'Capacity', value: event.capacity != null ? String(event.capacity) : '' },
    )
  }
  return rows.map((row) => ({
    ...row,
    empty: !row.value,
    value: row.value || 'Not provided',
  }))
}

function openDetails(event) {
  selected.value = event
}

function closeDetails() {
  selected.value = null
}

async function loadEvents() {
  loading.value = true
  error.value = ''
  try {
    // Server filters to submitted/under review/changes requested and orders
    // by submittedAt ascending (longest-waiting first). A coordinator gets
    // only their own requests; the Lead's "unassigned" filter is applied
    // client-side below (filteredEvents) against this list.
    const { data } = await getSubmissionQueue({ includeCompleted: includeCompleted.value })
    events.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load the review queue. Please try again.'
  } finally {
    loading.value = false
  }
}

async function loadCoordinatorNames() {
  try {
    const { data } = await getCoordinatorCandidates()
    coordinatorNames.value = Object.fromEntries(data.map((row) => [row.userId, row.name]))
  } catch {
    // Non-fatal - the queue shows coordinator ids instead.
  }
}

async function loadMyUserId() {
  try {
    const { data } = await getMe()
    myUserId.value = data.userId
  } catch {
    // Non-fatal - the "mine" filter just won't match anything.
  }
}

function removeFromQueue(eventId) {
  events.value = events.value.filter((event) => event.eventId !== eventId)
  if (selected.value?.eventId === eventId) selected.value = null
}

// Approved requests move to planning, which is no longer in the queue.
function onApproved(approved) {
  approving.value = null
  removeFromQueue(approved.eventId)
}

// Assigning moves a submitted request to "under review" and sets its
// coordinator, so reload the queue and keep the open popup in step.
async function onAssigned(assignment) {
  assigning.value = null
  await loadEvents()
  if (selected.value?.eventId === assignment.eventId) {
    selected.value = events.value.find((event) => event.eventId === assignment.eventId) || null
  }
}

function openReject(event) {
  rejecting.value = event
  rejectReason.value = ''
  rejectExplanation.value = ''
}

async function confirmReject() {
  const event = rejecting.value
  busyIds.add(event.eventId)
  delete rowErrors[event.eventId]
  try {
    await rejectEvent(event.eventId, rejectReason.value, rejectExplanation.value.trim())
    removeFromQueue(event.eventId)
    rejecting.value = null
  } catch (err) {
    rowErrors[event.eventId] = err.response?.data?.detail || 'Could not reject this event.'
    rejecting.value = null
  } finally {
    busyIds.delete(event.eventId)
  }
}

onMounted(() => {
  loadEvents()
  loadMyUserId()
  if (isLead.value) loadCoordinatorNames()
  ticker = setInterval(() => { now.value = Date.now() }, 60000)
})
onUnmounted(() => clearInterval(ticker))
</script>

<style scoped>
.review-queue { display: flex; flex-direction: column; gap: 16px; width: 100%; }

.queue-toolbar { display: flex; flex-direction: column; gap: 14px; }
.search {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.search input {
  width: 100%;
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  padding: 9px 12px;
  color-scheme: dark;
}
.search input:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .5);
}
.queue-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.filter-btn {
  background: var(--glass);
  border: 1px solid var(--hairline);
  color: var(--muted);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12px;
  cursor: pointer;
  transition: border-color .3s var(--ease-out), color .3s var(--ease-out), background .3s var(--ease-out);
}
.include-completed { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); cursor: pointer; }
.filter-btn:hover { border-color: rgba(167, 139, 250, .4); color: var(--text); }
.filter-btn.active {
  color: var(--text);
  border-color: rgba(167, 139, 250, .6);
  background: rgba(124, 77, 255, .18);
}

.empty-note { font-size: 14px; color: var(--muted); }

.event-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.event-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  min-height: 176px;
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 18px 20px;
  cursor: pointer;
  transition: border-color .4s var(--ease-out), background .4s var(--ease-out);
}
.event-card:focus-visible { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }
.event-card:hover { border-color: rgba(167, 139, 250, .3); background: var(--glass-strong); }
.event-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.event-name-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-width: 0; }
.event-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 16px; line-height: 1.35; }
.event-org { font-size: 13px; color: var(--body); }
.event-when,
.event-wait { font-size: 13px; color: var(--muted); line-height: 1.45; }
.event-facts { display: flex; flex-wrap: wrap; gap: 8px; }
.event-facts span,
.event-assignee {
  font-size: 12px;
  color: var(--body);
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 3px 9px;
}

.near-flag {
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #FF8A76;
  background: rgba(255, 138, 118, .12);
  border: 1px solid rgba(255, 138, 118, .3);
  border-radius: 999px;
  padding: 2px 8px;
}

.actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: auto; }

.status-pill {
  flex-shrink: 0;
  display: inline-block;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--halo);
  background: rgba(124, 77, 255, .18);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 999px;
  padding: 3px 10px;
}

.row-error { color: #FF8A76; font-size: 12px; margin: 10px 0 0; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}

.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(5, 2, 14, .7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center; z-index: 10;
}
.modal {
  background: linear-gradient(160deg, #1A0C3B, #0D0524);
  border: 1px solid rgba(167, 139, 250, .28);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
  border-radius: 18px;
  padding: 30px;
  width: 360px;
}
.modal h3 { margin: 0 0 20px; font-size: 18px; font-weight: 500; }
.modal label {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); display: block; margin-bottom: 6px;
}
.modal select,
.modal textarea {
  width: 100%;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: 9px;
  padding: 11px 12px;
  font-size: 14px;
  color: var(--text);
  font-family: 'Inter', sans-serif;
  resize: vertical;
  line-height: 1.6;
}
.modal select { margin-bottom: 16px; }
.modal select:focus,
.modal textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }

.btn:disabled { opacity: .55; cursor: progress; }

/* Details popup */
.details-modal {
  width: min(880px, calc(100vw - 48px));
  max-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  padding: 26px 28px;
}
.details-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 18px; }
.details-head h3 { margin: 0 0 8px; }
.close-btn {
  background: none; border: 1px solid var(--hairline); color: var(--body);
  width: 32px; height: 32px; border-radius: 50%; font-size: 18px; line-height: 1;
  cursor: pointer; flex-shrink: 0;
}
.close-btn:hover { background: rgba(167, 139, 250, .1); color: var(--text); }
.details-body { overflow-y: auto; padding-right: 6px; }
.detail-row {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: 4px 16px;
  padding: 10px 0;
  border-top: 1px solid var(--hairline);
}
.detail-row:first-child { border-top: none; }
.detail-row dt {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); padding-top: 2px;
}
.detail-row dd { margin: 0; font-size: 14px; color: var(--text); line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.detail-row dd.empty { color: var(--muted); font-style: italic; }
.details-body dl {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 28px;
}
.detail-row.wide { grid-column: 1 / -1; }
.details-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--hairline); }

@media (max-width: 900px) {
  .event-list { grid-template-columns: 1fr; }
  .details-body dl { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .detail-row { grid-template-columns: 1fr; }
}
</style>
