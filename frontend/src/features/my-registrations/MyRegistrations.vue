<template>
  <div class="my-registrations">
    <p v-if="loading" class="empty-note">Loading your registrations…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <div v-else-if="!rows.length" data-testid="my-registrations-empty">
      <p class="empty-note">You have no registrations yet. Browse events to find one.</p>
      <button type="button" class="btn btn-solid" data-testid="empty-browse-events" @click="browse">
        Browse events
      </button>
    </div>
    <template v-else>
      <section v-for="group in groups" :key="group.id" :data-testid="group.id">
        <h3>{{ group.title }}</h3>
        <p v-if="!group.rows.length" class="empty-note group-empty">{{ group.empty }}</p>
        <div v-else class="cards">
          <button
            v-for="row in group.rows"
            :key="row.attendeeRegistrationId"
            type="button"
            class="event-card"
            :data-testid="`my-registration-${row.eventId}`"
            :data-cancelled="row.cancelled ? 'true' : 'false'"
            :data-changed="row.changed ? 'true' : 'false'"
            @click="open(row.attendeeRegistrationId)"
          >
            <span class="event-name" :title="row.eventName || row.eventId">{{ row.eventName || row.eventId }}</span>
            <span class="event-facts">
              <span class="fact">
                <span class="fact-label">Category:</span>
                <span>{{ row.category }}</span>
              </span>
              <span class="fact" :class="{ flagged: row.dateChanged }">
                <span class="fact-label">Date:</span>
                <span class="fact-value">
                  <span data-testid="reg-date">{{ datePart(row.proposedStartAt || row.startsAt) }}</span>
                  <span v-if="row.dateChanged" class="change-flag">Date changed</span>
                </span>
              </span>
              <span class="fact" :class="{ flagged: row.timeChanged }">
                <span class="fact-label">Time:</span>
                <span class="fact-value">
                  <span data-testid="reg-start">{{ timePart(row.proposedStartAt || row.startsAt) }}</span>
                  – <span data-testid="reg-end">{{ timePart(row.proposedEndAt || row.endsAt) }}</span> SGT
                  <span v-if="row.timeChanged" class="change-flag">Time changed</span>
                </span>
              </span>
              <span class="fact" :class="{ flagged: row.venueChanged }">
                <span class="fact-label">Location:</span>
                <span class="fact-value">
                  <span>{{ [row.venueName, row.venueLocation].filter(Boolean).join(' · ') || 'To be confirmed' }}</span>
                  <span v-if="row.venueChanged" class="change-flag">Location changed</span>
                </span>
              </span>
            </span>
            <span class="status">
              {{ row.cancelled ? 'Cancelled' : row.status }}
              <template v-if="row.changed && !row.dateChanged && !row.timeChanged && !row.venueChanged"> · Changed</template>
            </span>
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
import { formatSgtDate, formatSgtTime, parseServerTime } from '../../utils/datetime.js'

const router = useRouter()
const rows = ref([])
const loading = ref(true)
const error = ref('')

// Upcoming soonest first; past most recent first.
const upcoming = computed(() => rows.value.filter((row) => !isPast(row)).sort(byStart))
const past = computed(() => rows.value.filter((row) => isPast(row)).sort((a, b) => byStart(b, a)))
const groups = computed(() => [
  { id: 'my-registrations-upcoming', title: 'Upcoming', rows: upcoming.value, empty: 'No upcoming registrations.' },
  { id: 'my-registrations-past', title: 'Past', rows: past.value, empty: 'No past registrations.' },
])

function startTime(row) {
  const start = row.proposedStartAt || row.startsAt
  return start ? parseServerTime(start).getTime() : Infinity
}

function byStart(a, b) {
  return startTime(a) - startTime(b)
}

function isPast(row) {
  const end = row.proposedEndAt || row.endsAt || row.proposedStartAt || row.startsAt
  if (!end) return false
  return parseServerTime(end).getTime() < Date.now()
}

function datePart(value) {
  return formatSgtDate(value)
}

function timePart(value) {
  return formatSgtTime(value)
}

function open(registrationId) {
  router.push(`/app/registrations/${registrationId}`)
}

function browse() {
  router.push('/app')
}

onMounted(async () => {
  try {
    const response = await getMyRegistrations()
    rows.value = response.data
  } catch (err) {
    const message = err.response?.data?.detail
    error.value = typeof message === 'string' ? message : 'Could not load your registrations.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.my-registrations, section { display: flex; flex-direction: column; gap: 12px; }
.empty-note { font-size: 14px; color: var(--muted); }
.group-empty { margin: 0; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
}
/* Registrations sit three to a row so the page uses its full width. */
.cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
@media (max-width: 1100px) {
  .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 720px) {
  .cards { grid-template-columns: minmax(0, 1fr); }
}
.event-card {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
  text-align: left;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: 18px 20px;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.event-name {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin: 0 0 12px;
  font-family: var(--font);
  font-size: 22px;
  font-weight: 500;
  letter-spacing: -.02em;
  color: var(--text);
}
.event-facts { display: flex; flex-direction: column; gap: 6px; }
.fact { display: flex; gap: 8px; font-size: 14px; line-height: 1.4; }
.fact-label { min-width: 84px; color: var(--muted); }
.fact-value { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }
.fact.flagged .fact-label { color: #FFD59A; }
.change-flag {
  font-size: 11px;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: #FFD59A;
}
/* Pinned to the bottom so the status lines up across a row of cards. */
.status { margin-top: auto; padding-top: 12px; font-size: 14px; color: var(--text); }
</style>
