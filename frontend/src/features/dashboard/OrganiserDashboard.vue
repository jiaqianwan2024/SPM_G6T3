<template>
  <div class="organiser-dashboard">
    <p v-if="loading" class="status-line full">Loading your events…</p>
    <UiAlert v-else-if="error" class="full" tone="danger">{{ error }}</UiAlert>

    <template v-else>
      <SectionBlock title="Needs your reply" :count="needsReply.length" data-testid="organiser-section-needs-reply">
        <p v-if="extrasLoading" class="status-line">Checking for replies…</p>
        <p v-else-if="!needsReply.length" class="quiet" data-testid="organiser-needs-reply-empty">
          Nothing needs your reply. When a coordinator asks a question, it shows up here first.
        </p>
        <ul v-else class="items">
          <li v-for="item in preview('reply', needsReply)" :key="item.event.eventId">
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
        <ShowMore v-if="!extrasLoading" :limit="PREVIEW_COUNT" label="replies" :total="needsReply.length" :open="expanded.reply" @toggle="toggle('reply')" />
      </SectionBlock>

      <SectionBlock v-if="needsAttention.length" title="Needs attention" :count="needsAttention.length"
                    data-testid="organiser-section-needs-attention">
        <EventList :events="preview('attention', needsAttention)" @open="open" />
        <ShowMore :limit="PREVIEW_COUNT" label="events" :total="needsAttention.length" :open="expanded.attention" @toggle="toggle('attention')" />
      </SectionBlock>

      <SectionBlock title="Change requests" :count="pendingChanges.length" data-testid="organiser-section-change-requests">
        <p v-if="extrasLoading" class="status-line">Checking for change requests…</p>
        <p v-else-if="!pendingChanges.length && !changeOutcomes.length" class="quiet"
           data-testid="organiser-change-requests-empty">
          No change requests. Ask for a change from an event's page once it is under review or confirmed.
        </p>
        <ul v-else class="items">
          <li v-for="c in pendingChanges" :key="c.changeRequestId">
            <button type="button" class="item" data-testid="organiser-change-pending" @click="open(c.eventId)">
              <span class="item-title">{{ c.reason }}</span>
              <span class="item-meta">{{ eventName(c.eventId) }} · waiting for the coordinator</span>
            </button>
          </li>
          <li v-for="c in preview('outcomes', changeOutcomes)" :key="c.changeRequestId">
            <button type="button" class="item" data-testid="organiser-change-outcome" @click="open(c.eventId)">
              <span class="item-title">{{ c.reason }}</span>
              <span class="item-meta">
                {{ eventName(c.eventId) }} · {{ outcomeLabel(c.status) }}
                <template v-if="c.decisionReason"> — {{ c.decisionReason }}</template>
              </span>
            </button>
          </li>
        </ul>
        <ShowMore v-if="!extrasLoading" :limit="PREVIEW_COUNT" :total="changeOutcomes.length" :open="expanded.outcomes" label="past decisions"
                  @toggle="toggle('outcomes')" />
      </SectionBlock>

      <SectionBlock title="Awaiting review" :count="awaitingReview.length" data-testid="organiser-section-awaiting-review">
        <p v-if="extrasLoading && !awaitingReview.length" class="status-line">Loading requests…</p>
        <UiEmptyState v-else-if="!awaitingReview.length && !events.length" title="No requests awaiting review"
                      hint="Create your first request to get started."
                      data-testid="organiser-awaiting-review-empty">
          <UiButton data-testid="organiser-empty-first-request" @click="$emit('open-tab', 'New Request')">
            Create your first request
          </UiButton>
        </UiEmptyState>
        <p v-else-if="!awaitingReview.length" class="quiet" data-testid="organiser-awaiting-review-empty">
          No requests awaiting review. Submitted requests wait here until a coordinator decides.
        </p>
        <EventList v-else :events="preview('awaiting', awaitingReview)" @open="open" />
        <ShowMore :limit="PREVIEW_COUNT" label="requests" :total="awaitingReview.length" :open="expanded.awaiting" @toggle="toggle('awaiting')" />
      </SectionBlock>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getClarifications,
  getMyChangeRequests,
  getMyEvents,
} from '../../api/eventService.js'
import { EVENT_STAGES } from '../../config/eventStatus.js'
import SectionBlock from '../../components/layout/SectionBlock.vue'
import UiAlert from '../../components/ui/UiAlert.vue'
import UiButton from '../../components/ui/UiButton.vue'
import UiEmptyState from '../../components/ui/UiEmptyState.vue'
import EventList from './OrganiserEventList.vue'
import ShowMore from './OrganiserShowMore.vue'

defineEmits(['open-tab'])

const router = useRouter()

// Events in each group, by plain-language stage. "draft" lives under My Events.
const stageStatuses = (key) => EVENT_STAGES.find((stage) => stage.key === key).statuses
const AWAITING_STATUSES = stageStatuses('in-review')
const PREPARATION_STATUSES = stageStatuses('in-preparation')

const events = ref([])
const clarifications = ref({}) // eventId -> open clarifications
const changeRequests = ref([])
const loading = ref(true)
const extrasLoading = ref(true) // clarifications and change requests arrive after the event list
const error = ref('')

// The dashboard previews each list. Showing the rest is one click, so it never floods the page.
const PREVIEW_COUNT = 3
const expanded = reactive({ reply: false, attention: false, outcomes: false, awaiting: false })
const toggle = (key) => { expanded[key] = !expanded[key] }
const preview = (key, list) => (expanded[key] ? list : list.slice(0, PREVIEW_COUNT))

const bySoonestStart = (a, b) => new Date(a.proposedStartAt || 8.64e15) - new Date(b.proposedStartAt || 8.64e15)

const byStatus = (statuses) => events.value.filter((event) => statuses.includes(event.status))

// A confirmed event whose arrangements are being reconsidered, and a rejected request
// whose date has not passed: both are easy to miss from My Events alone.
const needsAttention = computed(() => [
  ...byStatus(['reconsidering']),
  ...byStatus(['rejected']).filter((event) => !event.proposedStartAt || new Date(event.proposedStartAt) > new Date()),
])

// An open clarification on an event still in review or preparation is waiting on the organiser.
// One on an event that has already left review (confirmed, closed) is not shown here.
const awaitsReply = (event) =>
  event.hasOpenClarifications && [...AWAITING_STATUSES, ...PREPARATION_STATUSES].includes(event.status)

const needsReply = computed(() =>
  events.value
    .map((event) => ({ event, clarifications: clarifications.value[event.eventId] || [] }))
    .filter((item) => item.clarifications.length),
)
const needsReplyIds = computed(() => new Set(needsReply.value.map((item) => item.event.eventId)))
// Still being reviewed or prepared: one "Awaiting review" list, review stages first. An event with an
// open clarification belongs under Needs your reply instead; until those threads load, the event's own
// flag says which, so nothing jumps between the two lists.
const awaitingReview = computed(() =>
  [...byStatus(AWAITING_STATUSES), ...byStatus(PREPARATION_STATUSES)]
    .filter((event) => (extrasLoading.value ? !awaitsReply(event) : !needsReplyIds.value.has(event.eventId)))
    .sort(bySoonestStart),
)

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

// The event list shows as soon as it arrives. The clarification and change-request lookups fill in
// afterwards, and a failed lookup doesn't blank the dashboard.
async function load() {
  loading.value = true
  extrasLoading.value = true
  error.value = ''
  try {
    const { data } = await getMyEvents()
    events.value = data
    loading.value = false

    // Only events that say they have an open clarification need their thread fetched, and all
    // change requests come in one call, so the number of requests doesn't grow with the events.
    const inReview = data.filter(awaitsReply)
    const [clarificationResults, changeResult] = await Promise.all([
      Promise.allSettled(inReview.map((event) => getClarifications(event.eventId))),
      getMyChangeRequests().catch(() => ({ data: [] })),
    ])

    const openByEvent = {}
    clarificationResults.forEach((result, i) => {
      if (result.status !== 'fulfilled') return
      const list = result.value.data.filter((c) => c.status === 'open')
      if (list.length) openByEvent[inReview[i].eventId] = list
    })
    clarifications.value = openByEvent
    changeRequests.value = changeResult.data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load your dashboard. Please try again.'
  } finally {
    loading.value = false
    extrasLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* One column on narrow screens; on wide ones the sections sit two abreast so no card
   stretches across the whole page and no half of the page is left empty. */
.organiser-dashboard {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: var(--space-5) var(--space-6);
  /* Every card here, in either column and in OrganiserEventList, is this tall, so rows line up. */
  --card-height: 84px;
}
@media (min-width: 1100px) {
  .organiser-dashboard { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.full { grid-column: 1 / -1; }
.status-line { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.quiet { margin: 0; color: var(--muted); font-size: var(--fs-sm); }


.items { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.item {
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--space-1);
  min-height: var(--card-height);
  padding: var(--space-3) var(--space-5);
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
</style>
