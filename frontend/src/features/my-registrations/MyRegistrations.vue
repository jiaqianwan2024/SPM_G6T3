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
          <span class="event-name">{{ row.eventName || row.eventId }}</span>
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
                <span>{{ row.venueName }} · {{ row.venueLocation }}</span>
                <span v-if="row.venueChanged" class="change-flag">Location changed</span>
              </span>
            </span>
          </span>
          <span class="status">
            {{ row.cancelled ? 'Cancelled' : row.status }}
            <template v-if="row.changed && !row.dateChanged && !row.timeChanged && !row.venueChanged"> · Changed</template>
          </span>
        </button>
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

const upcoming = computed(() => rows.value.filter((row) => !isPast(row)))
const past = computed(() => rows.value.filter((row) => isPast(row)))
const groups = computed(() => [
  { id: 'my-registrations-upcoming', title: 'Upcoming', rows: upcoming.value },
  { id: 'my-registrations-past', title: 'Past', rows: past.value },
])

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
.form-error {
  color: #FF8A76;
  font-size: 13px;
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}
.event-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
  text-align: left;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  padding: 18px 20px;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.event-name {
  margin: 0 0 12px;
  font-family: 'Space Grotesk', sans-serif;
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
.status { margin-top: 12px; font-size: 14px; color: var(--text); }
</style>
