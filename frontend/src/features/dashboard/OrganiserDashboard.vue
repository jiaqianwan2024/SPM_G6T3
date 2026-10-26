<template>
  <div class="organiser-dashboard">
    <p v-if="loading" class="status-line">Loading your events…</p>
    <UiAlert v-else-if="error" tone="danger">{{ error }}</UiAlert>

    <template v-else>
      <div class="top">
        <StatGrid class="stats">
          <StatCard label="Needs your reply" :value="needsReply.length" hint="Open clarifications" />
          <StatCard label="Awaiting review" :value="awaitingReview.length" />
          <StatCard label="Confirmed" :value="confirmed.length" />
          <StatCard label="Pending changes" :value="pendingChanges.length" />
        </StatGrid>
        <UiButton data-testid="organiser-new-request" @click="$emit('open-tab', 'New Request')">
          New request
        </UiButton>
      </div>

      <UiCard v-if="!events.length" class="first" data-testid="organiser-first-request-card">
        <p class="first-title">Create your first request to get started.</p>
        <p class="first-hint">Tell us what you're planning and a coordinator will pick it up.</p>
        <UiButton data-testid="organiser-empty-first-request" @click="$emit('open-tab', 'New Request')">
          Create your first request
        </UiButton>
      </UiCard>

      <SectionBlock title="Needs your reply" :count="needsReply.length" data-testid="organiser-section-needs-reply">
        <UiEmptyState v-if="!needsReply.length" title="Nothing needs your reply"
                      hint="When a coordinator asks a question, it shows up here first."
                      data-testid="organiser-needs-reply-empty" />
        <ul v-else class="items">
          <li v-for="item in needsReply" :key="item.event.eventId">
            <button type="button" class="item attention" :data-testid="`organiser-needs-reply-${item.event.eventId}`"
                    @click="open(item.event.eventId)">
              <span class="item-title">{{ item.event.eventName || 'Untitled event' }}</span>
              <span v-for="c in item.clarifications" :key="c.clarificationId" class="item-body">
                {{ c.message }}
              </span>
              <span class="item-meta">Open the event to reply</span>
            </button>
          </li>
        </ul>
      </SectionBlock>

      <SectionBlock title="Awaiting review" :count="awaitingReview.length" data-testid="organiser-section-awaiting-review">
        <UiEmptyState v-if="!awaitingReview.length" title="No requests awaiting review"
                      hint="Submitted requests wait here until a coordinator decides."
                      data-testid="organiser-awaiting-review-empty" />
        <EventList v-else :events="awaitingReview" @open="open" />
      </SectionBlock>

      <SectionBlock v-if="inPreparation.length" title="In preparation" :count="inPreparation.length"
                    data-testid="organiser-section-in-preparation">
        <EventList :events="inPreparation" @open="open" />
      </SectionBlock>

      <SectionBlock title="Confirmed" :count="confirmed.length" data-testid="organiser-section-confirmed">
        <UiEmptyState v-if="!confirmed.length" title="No confirmed events yet"
                      hint="Once venue, equipment and safety are settled, your event appears here."
                      data-testid="organiser-confirmed-empty" />
        <EventList v-else :events="confirmed" @open="open" />
      </SectionBlock>

      <SectionBlock title="Change requests" :count="pendingChanges.length" data-testid="organiser-section-change-requests">
        <UiEmptyState v-if="!pendingChanges.length && !changeOutcomes.length" title="No change requests"
                      hint="Ask for a change from an event's page once it is under review or confirmed."
                      data-testid="organiser-change-requests-empty" />
        <template v-else>
          <h4 class="sub">Pending</h4>
          <p v-if="!pendingChanges.length" class="muted">Nothing pending.</p>
          <ul v-else class="items">
            <li v-for="c in pendingChanges" :key="c.changeRequestId">
              <button type="button" class="item" data-testid="organiser-change-pending" @click="open(c.eventId)">
                <span class="item-title">{{ c.reason }}</span>
                <span class="item-meta">{{ eventName(c.eventId) }} · waiting for the coordinator</span>
              </button>
            </li>
          </ul>
          <h4 class="sub">Recent outcomes</h4>
          <p v-if="!changeOutcomes.length" class="muted">No decisions yet.</p>
          <ul v-else class="items">
            <li v-for="c in changeOutcomes" :key="c.changeRequestId">
              <button type="button" class="item" data-testid="organiser-change-outcome" @click="open(c.eventId)">
                <span class="item-title">{{ c.reason }}</span>
                <span class="item-meta">
                  {{ eventName(c.eventId) }} · {{ outcomeLabel(c.status) }}
                  <template v-if="c.decisionReason"> — {{ c.decisionReason }}</template>
                </span>
              </button>
            </li>
          </ul>
        </template>
      </SectionBlock>

      <SectionBlock title="Cancelled" :count="cancelled.length" data-testid="organiser-section-cancelled">
        <UiEmptyState v-if="!cancelled.length" title="No cancelled events"
                      data-testid="organiser-cancelled-empty" />
        <EventList v-else :events="cancelled" @open="open" />
      </SectionBlock>

      <SectionBlock v-if="past.length" title="Completed or closed" :count="past.length"
                    data-testid="organiser-section-past">
        <EventList :events="past" @open="open" />
      </SectionBlock>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getChangeRequests,
  getClarifications,
  getMyEvents,
} from '../../api/eventService.js'
import { IN_REVIEW_EVENT_STATUSES } from '../../config/eventStatus.js'
import SectionBlock from '../../components/layout/SectionBlock.vue'
import StatCard from '../../components/layout/StatCard.vue'
import StatGrid from '../../components/layout/StatGrid.vue'
import UiAlert from '../../components/ui/UiAlert.vue'
import UiButton from '../../components/ui/UiButton.vue'
import UiCard from '../../components/ui/UiCard.vue'
import UiEmptyState from '../../components/ui/UiEmptyState.vue'
import EventList from './OrganiserEventList.vue'

defineEmits(['open-tab'])

const router = useRouter()

// Events in each group, by plain-language stage. "draft" lives on the Drafts tab.
const AWAITING_STATUSES = ['submitted', 'under review', 'changes requested']
const PREPARATION_STATUSES = ['approved', 'planning', 'safety review', 'safety approved', 'preparing', 'prepared']
// A reconsidering event is still a confirmed one (see config/eventStatus.js).
const CONFIRMED_STATUSES = ['confirmed', 'reconsidering']
const PAST_STATUSES = ['completed', 'rejected']

const events = ref([])
const clarifications = ref({}) // eventId -> open clarifications
const changeRequests = ref([])
const loading = ref(true)
const error = ref('')

const byStatus = (statuses) => events.value.filter((event) => statuses.includes(event.status))
const startTime = (event) => new Date(event.proposedStartAt || 8.64e15).getTime()

const needsReply = computed(() =>
  byStatus(IN_REVIEW_EVENT_STATUSES)
    .map((event) => ({ event, clarifications: clarifications.value[event.eventId] || [] }))
    .filter((item) => item.clarifications.length),
)
const needsReplyIds = computed(() => new Set(needsReply.value.map((item) => item.event.eventId)))
const awaitingReview = computed(() =>
  byStatus(AWAITING_STATUSES).filter((event) => !needsReplyIds.value.has(event.eventId)),
)
const inPreparation = computed(() => byStatus(PREPARATION_STATUSES))
const confirmed = computed(() => [...byStatus(CONFIRMED_STATUSES)].sort((a, b) => startTime(a) - startTime(b)))
const cancelled = computed(() => byStatus(['cancelled']))
const past = computed(() => byStatus(PAST_STATUSES))

const pendingChanges = computed(() => changeRequests.value.filter((c) => c.status === 'pending'))
const changeOutcomes = computed(() =>
  changeRequests.value
    .filter((c) => c.status !== 'pending')
    .sort((a, b) => new Date(b.reviewedAt || b.createdAt) - new Date(a.reviewedAt || a.createdAt)),
)

const OUTCOMES = { accepted: 'Accepted', applied: 'Applied', declined: 'Declined', withdrawn: 'Withdrawn' }
const outcomeLabel = (status) => OUTCOMES[status] || status

function eventName(eventId) {
  return events.value.find((event) => event.eventId === eventId)?.eventName || 'Untitled event'
}

function open(eventId) {
  router.push(`/app/events/${eventId}`)
}

// The two lookups are per event, so one slow or failed event doesn't blank the dashboard.
async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getMyEvents()
    events.value = data

    const inReview = data.filter((event) => IN_REVIEW_EVENT_STATUSES.includes(event.status))
    const changeable = data.filter((event) => event.status !== 'draft')
    const [clarificationResults, changeResults] = await Promise.all([
      Promise.allSettled(inReview.map((event) => getClarifications(event.eventId))),
      Promise.allSettled(changeable.map((event) => getChangeRequests(event.eventId))),
    ])

    const openByEvent = {}
    clarificationResults.forEach((result, i) => {
      if (result.status !== 'fulfilled') return
      const list = result.value.data.filter((c) => c.status === 'open')
      if (list.length) openByEvent[inReview[i].eventId] = list
    })
    clarifications.value = openByEvent
    changeRequests.value = changeResults.flatMap((r) => (r.status === 'fulfilled' ? r.value.data : []))
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load your dashboard. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.organiser-dashboard { display: flex; flex-direction: column; gap: var(--space-5); }
.status-line { margin: 0; color: var(--muted); font-size: var(--fs-sm); }

.top { display: flex; align-items: flex-start; gap: var(--space-5); flex-wrap: wrap; }
.stats { flex: 1 1 520px; }

.first { text-align: center; }
.first-title { margin: 0; color: var(--text); font-size: var(--fs-lg); }
.first-hint { margin: var(--space-2) 0 var(--space-4); color: var(--muted); font-size: var(--fs-sm); }

.items { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.item {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-5);
  text-align: left;
  font: inherit;
  color: var(--body);
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color .3s var(--ease-out), background .3s var(--ease-out);
}
.item:hover { border-color: rgba(167, 139, 250, .4); background: var(--glass-strong); }
.item:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.item.attention { border-color: rgba(245, 196, 81, .45); }
.item-title { color: var(--text); font-size: var(--fs-md); font-weight: 500; }
.item-body { font-size: var(--fs-sm); }
.item-meta { font-size: var(--fs-xs); color: var(--muted); }

.sub { margin: var(--space-3) 0 var(--space-2); font-size: var(--fs-sm); font-weight: 500; color: var(--muted); }
.muted { margin: 0 0 var(--space-3); font-size: var(--fs-sm); color: var(--muted); }
</style>
