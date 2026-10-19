<template>
  <!-- Prototype: the Event Coordinator Lead's dashboard. Live counts, the
       requests waiting longest for a coordinator (assignable inline), and each
       coordinator's workload. Built only on the Lead's queue (SPM-117) and
       assignments (SPM-119) reads, so it can be reworked without backend changes. -->
  <div class="lead-dashboard" data-testid="lead-dashboard">
    <div class="counts">
      <div class="count" data-testid="lead-count-unassigned">
        <span class="count-value">{{ loaded ? unassigned.length : '–' }}</span>
        <span class="count-label">Unassigned requests</span>
      </div>
      <div class="count" data-testid="lead-count-oldest">
        <span class="count-value">{{ loaded ? oldestWait : '–' }}</span>
        <span class="count-label">Longest wait for a coordinator</span>
      </div>
      <div class="count" data-testid="lead-count-near">
        <span class="count-value">{{ loaded ? nearDate.length : '–' }}</span>
        <span class="count-label">Unassigned with a near date</span>
      </div>
      <div class="count" data-testid="lead-count-active">
        <span class="count-value">{{ loaded ? activeTotal : '–' }}</span>
        <span class="count-label">Active events across {{ loaded ? groups.length : '–' }} coordinators</span>
      </div>
    </div>

    <p v-if="notice" class="notice" data-testid="lead-dashboard-notice">{{ notice }}</p>
    <p v-if="loadError" class="form-error">{{ loadError }}</p>

    <section class="block">
      <div class="block-head">
        <h3>Waiting for a coordinator</h3>
        <button v-if="unassigned.length" type="button" class="link" @click="emit('open-tab', 'Review Queue')">
          See all in the Review Queue
        </button>
      </div>
      <p v-if="!loaded" class="empty-note">Loading…</p>
      <p v-else-if="!unassigned.length" class="empty-note" data-testid="lead-dashboard-empty">
        Every request has a coordinator. New requests appear here until you assign them.
      </p>
      <article
        v-for="event in waitingFirst"
        :key="event.eventId"
        class="item"
        :data-testid="`lead-waiting-${event.eventId}`"
      >
        <div class="item-main">
          <span class="item-name">{{ event.eventName }}</span>
          <span class="item-meta">
            <template v-if="event.organisationName">{{ event.organisationName }} · </template>
            {{ formatDate(event.proposedStartAt) }} · {{ event.expectedAttendance }} attendees ·
            <span class="wait">waiting {{ waitingFor(event.submittedAt) }}</span>
            <span v-if="event.dateNear" class="flag">Date is near</span>
          </span>
        </div>
        <button
          type="button"
          class="btn btn-outline small"
          :data-testid="`lead-assign-${event.eventId}`"
          @click="assigning = event"
        >
          Assign
        </button>
      </article>
      <p v-if="unassigned.length > WAITING_SHOWN" class="more">
        and {{ unassigned.length - WAITING_SHOWN }} more in the Review Queue
      </p>
    </section>

    <section class="block">
      <div class="block-head">
        <h3>Coordinator workload</h3>
        <button v-if="groups.length" type="button" class="link" @click="emit('open-tab', 'Assignments')">
          Open Assignments
        </button>
      </div>
      <p v-if="loaded && !groups.length" class="empty-note">There are no Event Coordinators yet.</p>
      <!-- One measure, one hue: bar length is the coordinator's active events,
           and the number is printed beside it, so nothing relies on the bar alone. -->
      <ul v-else class="workload">
        <li v-for="group in byWorkload" :key="group.userId">
          <button
            type="button"
            class="workload-row"
            :title="`${group.name}: ${group.events.length} active ${group.events.length === 1 ? 'event' : 'events'}`"
            :data-testid="`lead-workload-${group.userId}`"
            @click="emit('open-tab', 'Assignments')"
          >
            <span class="who">{{ group.name }}</span>
            <span class="track" aria-hidden="true">
              <span class="bar" :style="{ width: `${barWidth(group)}%` }"></span>
            </span>
            <span class="value" data-testid="lead-workload-count">{{ group.events.length }}</span>
          </button>
        </li>
      </ul>
    </section>

    <AssignCoordinatorDialog
      v-if="assigning"
      :event="assigning"
      @close="assigning = null"
      @assigned="onAssigned"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getCoordinatorAssignments, getSubmissionQueue } from '../../api/eventService.js'
import AssignCoordinatorDialog from '../event-detail/AssignCoordinatorDialog.vue'
import { formatSgt } from '../../utils/datetime.js'

// Opening the Review Queue or Assignments tab is the dashboard's way out.
const emit = defineEmits(['open-tab'])

const WAITING_SHOWN = 5

const queue = ref([])
const groups = ref([])
const loaded = ref(false)
const loadError = ref('')
const notice = ref('')
const assigning = ref(null)

// Ticks once a minute so the waiting times stay current without a reload.
const now = ref(Date.now())
let ticker = null

// The queue arrives longest-waiting first, so the unassigned ones keep that order.
const unassigned = computed(() => queue.value.filter((event) => !event.coordinatorId))
const waitingFirst = computed(() => unassigned.value.slice(0, WAITING_SHOWN))
const nearDate = computed(() => unassigned.value.filter((event) => event.dateNear))
const oldestWait = computed(() => (unassigned.value.length ? waitingFor(unassigned.value[0].submittedAt) : 'None'))
const activeTotal = computed(() => groups.value.reduce((sum, group) => sum + group.events.length, 0))
const byWorkload = computed(() =>
  [...groups.value].sort((a, b) => b.events.length - a.events.length || a.name.localeCompare(b.name)),
)
const busiest = computed(() => Math.max(1, ...groups.value.map((group) => group.events.length)))

function barWidth(group) {
  return (group.events.length / busiest.value) * 100
}

// submittedAt is stored in UTC without a zone marker; read it as UTC.
function parseUtc(value) {
  if (!value) return null
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`)
}

function waitingFor(submittedAt) {
  const start = parseUtc(submittedAt)
  if (!start) return 'unknown'
  const minutes = Math.max(0, Math.floor((now.value - start.getTime()) / 60000))
  if (minutes < 60) return minutes < 1 ? 'under a minute' : `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ${minutes % 60}m`
  return `${Math.floor(hours / 24)}d ${hours % 24}h`
}

function formatDate(value) {
  return value ? formatSgt(value) : 'No date set'
}

async function load() {
  loadError.value = ''
  try {
    const [queueResponse, assignmentsResponse] = await Promise.all([getSubmissionQueue(), getCoordinatorAssignments()])
    queue.value = queueResponse.data
    groups.value = assignmentsResponse.data
  } catch (err) {
    loadError.value = err.response?.data?.detail || 'Could not load the dashboard. Please try again.'
  } finally {
    loaded.value = true
  }
}

async function onAssigned(assignment) {
  const event = assigning.value
  assigning.value = null
  await load()
  const name = groups.value.find((group) => group.userId === assignment.coordinatorId)?.name || assignment.coordinatorId
  notice.value = `Assigned ${event.eventName} to ${name}.`
}

onMounted(() => {
  load()
  ticker = setInterval(() => { now.value = Date.now() }, 60000)
})
onUnmounted(() => clearInterval(ticker))
</script>

<style scoped>
.lead-dashboard { display: flex; flex-direction: column; gap: 18px; max-width: 900px; }

.counts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.count {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.count-value { font-family: 'Space Grotesk', sans-serif; font-size: 26px; color: var(--text); }
.count-label { font-size: 12px; color: var(--muted); letter-spacing: .04em; }

.block h3 { margin: 0; font-size: 15px; font-weight: 500; color: var(--text); }
.block-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 10px; }
.link { background: none; border: none; padding: 0; font: inherit; font-size: 13px; color: var(--halo); cursor: pointer; }
.link:hover { text-decoration: underline; }
.empty-note, .more { font-size: 14px; color: var(--muted); margin: 0; line-height: 1.6; }
.more { font-size: 13px; }

.item {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 14px;
  padding: 12px 18px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
}
.item-main { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.item-name { font-family: 'Space Grotesk', sans-serif; font-weight: 500; color: var(--text); font-size: 15px; }
.item-meta { font-size: 12px; color: var(--muted); line-height: 1.5; }
.wait { color: var(--body); }
.flag {
  display: inline-block;
  margin-left: 6px;
  vertical-align: 1px;
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #FFD9A8;
  border: 1px solid rgba(255, 196, 120, .35);
  border-radius: 999px;
  padding: 2px 8px;
}
.btn.small { padding: 7px 14px; font-size: 13px; flex-shrink: 0; }

.workload {
  list-style: none;
  margin: 0;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
}
.workload-row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(90px, 160px) 1fr 32px;
  align-items: center;
  gap: 12px;
  background: none;
  border: none;
  border-radius: 8px;
  padding: 8px 6px;
  font: inherit;
  color: var(--body);
  text-align: left;
  cursor: pointer;
}
.workload-row:hover, .workload-row:focus-visible { background: rgba(255, 255, 255, .04); outline: none; }
.who { font-size: 13px; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* A recessive track; the bar grows from the left baseline with a rounded data end. */
.track { height: 12px; background: rgba(255, 255, 255, .05); border-radius: 0 4px 4px 0; overflow: hidden; }
.bar { display: block; height: 100%; background: var(--iris-soft); border-radius: 0 4px 4px 0; min-width: 2px; }
.value { font-size: 13px; color: var(--text); text-align: right; font-variant-numeric: tabular-nums; }

.notice { font-size: 13px; color: var(--halo); background: rgba(124, 77, 255, .1); border: 1px solid rgba(167, 139, 250, .25); border-radius: 9px; padding: 11px 14px; margin: 0; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
  margin: 0;
}

@media (max-width: 720px) {
  .counts { grid-template-columns: repeat(2, 1fr); }
  .item { flex-direction: column; align-items: flex-start; }
}
</style>
