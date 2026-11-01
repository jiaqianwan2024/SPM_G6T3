<template>
  <!-- SPM-120: the Safety Officer's home. Their own claimed reviews, the unclaimed
       ones awaiting a decision (newest first), and recent decisions. Each item
       opens inline with the full proposed event and the decision, or links to the
       event page. Only safety-review reads are used, so the server's RBAC (Safety
       Officers only; only the claiming officer decides) applies to every list. -->
  <div class="safety-dashboard" data-testid="safety-dashboard">
    <UiSkeleton v-if="!loaded" :lines="4" height="72px" />
    <UiAlert v-else-if="loadError" tone="danger">{{ loadError }}</UiAlert>

    <template v-else>
      <div class="top">
        <StatGrid class="stats">
          <StatCard label="Your open reviews" :value="mine.length" data-testid="safety-count-mine" />
          <StatCard label="Awaiting a decision" :value="awaiting.length" data-testid="safety-count-awaiting" />
          <StatCard v-for="count in DECIDED" :key="count.status" :label="count.label"
                    :value="lists[count.status].length" :data-testid="`safety-count-${count.status}`" />
        </StatGrid>
        <UiButton variant="outline" size="sm" data-testid="safety-dashboard-refresh" @click="load">Refresh</UiButton>
      </div>

      <UiAlert v-if="notice" tone="success" dismissible data-testid="safety-dashboard-notice" @dismiss="notice = ''">
        {{ notice }}
      </UiAlert>

      <SectionBlock v-for="section in sections" :key="section.key" :title="section.title"
                    :count="section.items.length" :data-testid="`safety-section-${section.key}`">
        <UiEmptyState v-if="!section.items.length" :title="section.emptyTitle" :hint="section.emptyHint"
                      :data-testid="`safety-${section.key}-empty`" />
        <ul v-else class="items">
          <li v-for="review in section.items" :key="review.reviewId">
            <UiCard as="article" class="item" :class="{ open: openId === review.reviewId }"
                    :data-testid="`safety-dashboard-item-${review.eventId}`">
              <div class="item-head">
                <div class="item-main">
                  <RouterLink :to="eventLink(review.eventId)" class="item-name"
                              :data-testid="`safety-dashboard-open-${review.eventId}`">
                    {{ review.package.eventName }}
                  </RouterLink>
                  <span class="item-meta">
                    {{ formatRange(review.package.proposedStartAt, review.package.proposedEndAt) }} ·
                    {{ review.package.expectedAttendance }} attendees · {{ venueSummary(review) }}
                  </span>
                  <span class="item-meta" :title="`Submitted ${formatSgt(review.submittedAt)}`"
                        :data-testid="`safety-dashboard-waiting-${review.eventId}`">
                    Submitted {{ formatTimeSince(review.submittedAt) }}
                    <template v-if="names[review.submittedBy]"> by {{ names[review.submittedBy] }}</template>
                  </span>
                  <span class="chips">
                    <span class="chip" :class="ownerClass(review)" :data-testid="`safety-dashboard-owner-${review.eventId}`">
                      {{ ownerLabel(review) }}
                    </span>
                    <span v-if="hasFlag(review)" class="chip warn">An arrangement is marked for re-checking</span>
                  </span>
                </div>
                <UiButton size="sm" :variant="openId === review.reviewId ? 'ghost' : 'solid'"
                          :aria-expanded="openId === review.reviewId"
                          :data-testid="`safety-dashboard-review-${review.eventId}`" @click="toggle(review)">
                  {{ openId === review.reviewId ? 'Close' : 'Review' }}
                </UiButton>
              </div>

              <div v-if="openId === review.reviewId" class="review">
                <h4>About the event</h4>
                <UiSkeleton v-if="!details[review.eventId]" :lines="3" />
                <p v-else-if="details[review.eventId] === FAILED" class="muted">
                  The full event record could not be loaded. The submitted safety facts are below.
                </p>
                <dl v-else class="facts" data-testid="safety-dashboard-event">
                  <div v-for="fact in eventFacts(details[review.eventId])" :key="fact.label" :class="{ wide: fact.wide }">
                    <dt>{{ fact.label }}</dt>
                    <dd>{{ fact.value }}</dd>
                  </div>
                </dl>

                <h4>Submitted for safety review</h4>
                <dl class="facts">
                  <template v-for="venue in review.package.venues" :key="venue.venueId">
                    <div>
                      <dt>Capacity in layout</dt>
                      <dd>{{ venue.capacityInLayout }} ({{ venue.layout || 'largest layout' }}) at {{ venue.venueName }}</dd>
                    </div>
                    <div>
                      <dt>Expected attendance</dt>
                      <dd :class="{ warn: review.package.expectedAttendance > venue.capacityInLayout }">
                        {{ review.package.expectedAttendance }}
                      </dd>
                    </div>
                    <div class="wide">
                      <dt>Emergency access</dt>
                      <dd>{{ venue.emergencyAccess || 'Not recorded for this venue' }}</dd>
                    </div>
                    <div class="wide">
                      <dt>Known venue restrictions</dt>
                      <dd>{{ venue.restrictions || 'None recorded' }}</dd>
                    </div>
                    <div class="wide">
                      <dt>Venue accessibility</dt>
                      <dd>{{ venue.accessibilityFeatures.join(', ') || 'None listed' }}</dd>
                    </div>
                    <div v-if="venue.needsReverification" class="wide">
                      <dt>Marked for re-checking</dt>
                      <dd class="warn">{{ venue.reverificationNote }}</dd>
                    </div>
                  </template>
                  <div class="wide">
                    <dt>Accessibility requirements</dt>
                    <dd>
                      {{ review.package.accessibilityRequirements.join(', ') || 'None' }}
                      <template v-if="review.package.accessibilityNote"> · {{ review.package.accessibilityNote }}</template>
                    </dd>
                  </div>
                  <div class="wide">
                    <dt>Equipment</dt>
                    <dd>
                      <template v-if="review.package.equipment.length">
                        <span v-for="line in review.package.equipment" :key="line.equipmentId" class="line">
                          {{ line.quantity }} × {{ line.name }}
                          <template v-if="line.technicalRequirements"> · {{ line.technicalRequirements }}</template>
                          <span v-if="line.needsReverification" class="warn"> · marked for re-checking</span>
                        </span>
                      </template>
                      <template v-else>No equipment requested</template>
                    </dd>
                  </div>
                  <div class="wide">
                    <dt>Equipment placement</dt>
                    <dd>{{ review.package.equipmentPlacement || 'No equipment to place' }}</dd>
                  </div>
                  <div class="wide">
                    <dt>Crowd movement</dt>
                    <dd>{{ review.package.crowdMovement }}</dd>
                  </div>
                </dl>
                <RouterLink class="full-link" :to="eventLink(review.eventId)">Open the full event page →</RouterLink>

                <!-- One Safety Officer per event: claim it first; only they decide (the server refuses anyone else). -->
                <div v-if="!review.safetyOfficerId" class="decision">
                  <p class="muted">Nobody has claimed this review yet. Claim it to decide; later rounds of this event come to you too.</p>
                  <UiAlert v-if="actionError" tone="danger">{{ actionError }}</UiAlert>
                  <div class="actions">
                    <UiButton size="sm" :loading="busy" data-testid="safety-dashboard-claim" @click="claim(review)">
                      Claim review
                    </UiButton>
                  </div>
                </div>
                <p v-else-if="!isMine(review)" class="muted" data-testid="safety-dashboard-claimed">
                  {{ nameOf(review.safetyOfficerId, 'Another Safety Officer') }} is reviewing this event, so only they can decide on it.
                </p>

                <div v-else class="decision">
                  <UiField label="Notes for the coordinator" hint="Optional to approve; required to reject or request changes."
                           v-slot="f">
                    <UiTextarea v-model="decisionText" v-bind="f" :rows="3" maxlength="4000"
                                data-testid="safety-dashboard-text" />
                  </UiField>
                  <fieldset class="affected">
                    <legend>If requesting changes, review again:</legend>
                    <label><input v-model="affected" type="checkbox" value="venue" data-testid="safety-dashboard-affected-venue" /> Venue</label>
                    <label><input v-model="affected" type="checkbox" value="technical" data-testid="safety-dashboard-affected-technical" /> Equipment</label>
                  </fieldset>
                  <UiAlert v-if="actionError" tone="danger">{{ actionError }}</UiAlert>
                  <div class="actions">
                    <UiButton variant="danger" size="sm" :disabled="busy || !decisionText.trim()"
                              data-testid="safety-dashboard-reject" @click="decide(review, 'reject')">
                      Reject
                    </UiButton>
                    <UiButton variant="outline" size="sm" :disabled="busy || !decisionText.trim()"
                              data-testid="safety-dashboard-request-changes" @click="decide(review, 'changes')">
                      Request changes
                    </UiButton>
                    <UiButton size="sm" :loading="busy" data-testid="safety-dashboard-approve" @click="decide(review, 'approve')">
                      Approve
                    </UiButton>
                  </div>
                </div>
              </div>
            </UiCard>
          </li>
        </ul>
        <p v-if="section.key === 'awaiting' && othersClaimed.length" class="muted others" data-testid="safety-others-claimed">
          {{ othersClaimed.length === 1 ? '1 more review is' : `${othersClaimed.length} more reviews are` }}
          being handled by another Safety Officer.
        </p>
      </SectionBlock>

      <SectionBlock title="Recently decided" :count="recent.length" data-testid="safety-section-decided">
        <UiEmptyState v-if="!recent.length" title="No decisions yet"
                      hint="Reviews you and other Safety Officers decide show up here."
                      data-testid="safety-decided-empty" />
        <ul v-else class="recent">
          <li v-for="review in recent" :key="review.reviewId" :data-testid="`safety-dashboard-decided-${review.eventId}`">
            <StatusPill :status="review.status.replace('_', ' ')" />
            <RouterLink :to="eventLink(review.eventId)">{{ review.package.eventName }}</RouterLink>
            <span class="muted">{{ formatSgt(review.decidedAt) }}</span>
            <span v-if="review.decisionNote" class="muted note">· {{ review.decisionNote }}</span>
          </li>
        </ul>
      </SectionBlock>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  approveSafetyReview,
  claimSafetyReview,
  getEvent,
  getSafetyReviewQueue,
  rejectSafetyReview,
  requestSafetyChanges,
} from '../../api/eventService.js'
import { getUsers } from '../../api/userService.js'
import { session } from '../../store/session.js'
import { formatSgt, formatSgtRange, formatTimeSince, parseServerTime } from '../../utils/datetime.js'
import SectionBlock from '../../components/layout/SectionBlock.vue'
import StatCard from '../../components/layout/StatCard.vue'
import StatGrid from '../../components/layout/StatGrid.vue'
import StatusPill from '../../components/ui/StatusPill.vue'
import UiAlert from '../../components/ui/UiAlert.vue'
import UiButton from '../../components/ui/UiButton.vue'
import UiCard from '../../components/ui/UiCard.vue'
import UiEmptyState from '../../components/ui/UiEmptyState.vue'
import UiField from '../../components/ui/UiField.vue'
import UiSkeleton from '../../components/ui/UiSkeleton.vue'
import UiTextarea from '../../components/ui/UiTextarea.vue'

const STATUSES = ['pending', 'approved', 'changes_requested', 'rejected']
const DECIDED = [
  { status: 'approved', label: 'Approved' },
  { status: 'changes_requested', label: 'Changes requested' },
  { status: 'rejected', label: 'Rejected' },
]
const FAILED = 'failed'

const lists = reactive({ pending: [], approved: [], changes_requested: [], rejected: [] })
const details = reactive({}) // eventId -> the full event record, or FAILED
const loaded = ref(false)
const loadError = ref('')
const openId = ref('')
const decisionText = ref('')
const affected = ref([])
const busy = ref(false)
const actionError = ref('')
const notice = ref('')
const names = ref({})

const submitted = (review) => parseServerTime(review.submittedAt)?.getTime() ?? 0

// Claimed by this officer and still undecided, longest-waiting first (the queue's own order).
const mine = computed(() => lists.pending.filter(isMine))
// Unclaimed, so any Safety Officer can take it; newest first.
const awaiting = computed(() =>
  lists.pending.filter((review) => !review.safetyOfficerId).sort((a, b) => submitted(b) - submitted(a)),
)
// Another officer's: only they can decide, so it isn't work for this one.
const othersClaimed = computed(() => lists.pending.filter((review) => review.safetyOfficerId && !isMine(review)))

const sections = computed(() => [
  {
    key: 'mine',
    title: 'Your reviews',
    items: mine.value,
    emptyTitle: 'No reviews waiting on you',
    emptyHint: 'Reviews you claim stay here until you decide on them.',
  },
  {
    key: 'awaiting',
    title: 'Awaiting a decision',
    items: awaiting.value,
    emptyTitle: 'Nothing is awaiting a decision',
    emptyHint: 'Events appear here once their venue and equipment are confirmed and the coordinator submits them.',
  },
])

// The five most recent decisions of any kind, newest first.
const recent = computed(() =>
  DECIDED.flatMap((count) => lists[count.status])
    .sort((a, b) => (parseServerTime(b.decidedAt)?.getTime() ?? 0) - (parseServerTime(a.decidedAt)?.getTime() ?? 0))
    .slice(0, 5),
)

const eventLink = (eventId) => `/app/events/${eventId}`

function formatRange(start, end) {
  if (!start || !end) return 'Date not set'
  return formatSgtRange(start, end)
}

function venueSummary(review) {
  return review.package.venues.map((venue) => venue.venueName).join(', ') || 'No venue'
}

// The proposed event as the organiser described it, beyond the safety facts.
function eventFacts(event) {
  return [
    { label: 'Organisation', value: event.organisationName },
    { label: 'Category', value: event.category },
    { label: 'Layout', value: event.layoutPreference },
    { label: 'Expected attendance', value: event.expectedAttendance },
    { label: 'Organiser contact', value: event.organiserContact, wide: true },
    { label: 'Purpose', value: event.purpose, wide: true },
    { label: 'Description', value: event.description, wide: true },
    { label: 'Venue requirements', value: event.venueRequirements, wide: true },
    { label: 'Facilities', value: event.requiredFacilities?.join(', '), wide: true },
    { label: 'Accessibility needs', value: event.accessibilityNeeds, wide: true },
    { label: 'Equipment notes', value: event.equipmentRequirements, wide: true },
  ].filter((fact) => fact.value !== undefined && fact.value !== null && fact.value !== '')
}

function hasFlag(review) {
  const { venues, equipment } = review.package
  return venues.some((venue) => venue.needsReverification) || equipment.some((line) => line.needsReverification)
}

function isMine(review) {
  return review.safetyOfficerId === session.userId
}

function nameOf(userId, fallback) {
  return names.value[userId] || fallback
}

function ownerLabel(review) {
  if (!review.safetyOfficerId) return 'Unclaimed'
  return isMine(review) ? 'Yours' : `Claimed by ${nameOf(review.safetyOfficerId, 'another Safety Officer')}`
}

function ownerClass(review) {
  if (!review.safetyOfficerId) return 'unclaimed'
  return isMine(review) ? 'mine' : 'taken'
}

function errorText(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return detail?.message || fallback
}

async function load() {
  loadError.value = ''
  try {
    const results = await Promise.all(STATUSES.map((status) => getSafetyReviewQueue(status)))
    STATUSES.forEach((status, index) => {
      lists[status] = results[index].data
    })
  } catch (err) {
    loadError.value = errorText(err, 'Could not load the safety reviews. Please try again.')
  } finally {
    loaded.value = true
  }
}

// The full event record is read when a review is opened, so the list loads fast.
async function loadDetails(eventId) {
  if (details[eventId]) return
  try {
    const { data } = await getEvent(eventId)
    details[eventId] = data
  } catch {
    details[eventId] = FAILED
  }
}

function toggle(review) {
  openId.value = openId.value === review.reviewId ? '' : review.reviewId
  decisionText.value = ''
  affected.value = []
  actionError.value = ''
  if (openId.value) loadDetails(review.eventId)
}

// Names are for display only; without them the dashboard still works.
async function loadNames() {
  try {
    const { data } = await getUsers()
    names.value = Object.fromEntries(data.map((user) => [user.userId, user.userName]))
  } catch {
    names.value = {}
  }
}

async function claim(review) {
  busy.value = true
  actionError.value = ''
  try {
    await claimSafetyReview(review.eventId, review.reviewId)
    notice.value = `You are now the Safety Officer for ${review.package.eventName}.`
    await load()
  } catch (err) {
    // A 409 names the officer who claimed it first.
    actionError.value = errorText(err, 'Could not claim the review. Please try again.')
  } finally {
    busy.value = false
  }
}

async function decide(review, kind) {
  busy.value = true
  actionError.value = ''
  const name = review.package.eventName
  try {
    if (kind === 'approve') {
      await approveSafetyReview(review.eventId, review.reviewId, decisionText.value)
      notice.value = `Approved ${name}. The coordinator can now confirm it.`
    } else if (kind === 'reject') {
      await rejectSafetyReview(review.eventId, review.reviewId, decisionText.value)
      notice.value = `Rejected ${name}. It is back in planning, and the coordinator and organiser have been told.`
    } else {
      await requestSafetyChanges(review.eventId, review.reviewId, decisionText.value, affected.value)
      notice.value = `Asked for changes to ${name}. It is back in planning until it is submitted again.`
    }
    openId.value = ''
    await load()
  } catch (err) {
    actionError.value = errorText(err, 'Could not record the decision. Please try again.')
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  load()
  loadNames()
})
</script>

<style scoped>
.safety-dashboard { display: flex; flex-direction: column; gap: var(--space-5); }

.top { display: flex; align-items: flex-start; gap: var(--space-5); flex-wrap: wrap; }
.stats { flex: 1 1 520px; }

.items { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.item { padding: var(--space-4) var(--space-5); transition: border-color .3s var(--ease-out); }
.item.open { border-color: rgba(167, 139, 250, .38); }
.item-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); }
.item-main { display: flex; flex-direction: column; gap: var(--space-1); min-width: 0; }
.item-name { color: var(--text); font-size: var(--fs-md); font-weight: 500; text-decoration: none; }
.item-name:hover { text-decoration: underline; }
.item-name:focus-visible { outline: none; box-shadow: var(--focus-ring); border-radius: var(--radius-sm); }
.item-meta { font-size: var(--fs-xs); color: var(--muted); line-height: 1.5; }

.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-1); }
.chip {
  padding: 2px 9px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--hairline);
  color: var(--muted);
  font-size: var(--fs-xs);
}
.chip.mine { color: var(--info); background: rgba(167, 139, 250, .1); border-color: currentColor; }
.chip.warn { color: var(--warning); background: rgba(245, 196, 81, .1); border-color: currentColor; }

.review { display: flex; flex-direction: column; gap: var(--space-3); border-top: 1px solid var(--hairline); margin-top: var(--space-4); padding-top: var(--space-4); }
h4 { margin: 0; font-size: var(--fs-sm); font-weight: 500; color: var(--text); }
.facts { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3) var(--space-5); margin: 0; }
.facts .wide { grid-column: 1 / -1; }
dt, legend { font-size: var(--fs-xs); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
dd { margin: 3px 0 0; font-size: var(--fs-sm); color: var(--body); line-height: 1.55; white-space: pre-wrap; }
.line { display: block; }
.warn { color: var(--warning); }
.full-link { align-self: flex-start; font-size: var(--fs-sm); color: var(--info); }

.decision { display: flex; flex-direction: column; gap: var(--space-3); }
.affected { border: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-5); align-items: center; }
.affected legend { padding: 0; margin-bottom: var(--space-2); }
.affected label { display: flex; align-items: center; gap: var(--space-2); font-size: var(--fs-sm); color: var(--body); }
.actions { display: flex; justify-content: flex-end; gap: var(--space-2); flex-wrap: wrap; }

.muted { margin: 0; font-size: var(--fs-sm); color: var(--muted); line-height: 1.55; }
.others { margin-top: var(--space-3); }

.recent { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.recent li { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: baseline; font-size: var(--fs-sm); color: var(--body); }
.recent a { color: var(--text); }
.note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 360px; }

@media (max-width: 720px) {
  .facts { grid-template-columns: 1fr; }
  .item-head { flex-direction: column; }
}
</style>
