<template>
  <div class="browse-detail">
    <button type="button" class="btn btn-ghost back" @click="back">← Browse events</button>

    <p v-if="loading" class="empty-note">Loading event…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>

    <template v-else-if="event">
      <header class="page-head">
        <p class="eyebrow">{{ event.category || 'Event' }}</p>
        <h1>{{ event.eventName }}</h1>
        <p v-if="schedule" class="when">{{ schedule }}</p>
      </header>

      <p v-if="event.description" class="lede" data-testid="browse-description">{{ event.description }}</p>
      <p v-else class="lede muted" data-testid="browse-description">No description yet.</p>

      <section class="panel">
        <dl class="facts">
          <div>
            <dt>Venue</dt>
            <dd>{{ venue }}</dd>
          </div>
          <div>
            <dt>Accessibility</dt>
            <dd data-testid="browse-accessibility">{{ event.accessibilityNeeds || 'None stated' }}</dd>
          </div>
          <div>
            <dt>Registration closes</dt>
            <dd data-testid="browse-closes-at">{{ closes }}</dd>
          </div>
          <div>
            <dt>Places</dt>
            <dd data-testid="browse-remaining" :class="{ full: event.full }">{{ places }}</dd>
          </div>
        </dl>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAttendeeCard, getOpenEvent } from '../../api/eventService.js'
import { formatSgt, formatSgtDate, formatSgtTime, parseServerTime } from '../../utils/datetime.js'

const route = useRoute()
const router = useRouter()
const event = ref(null)
const loading = ref(true)
const error = ref('')

const schedule = computed(() => {
  const start = event.value?.proposedStartAt || event.value?.startsAt
  const end = event.value?.proposedEndAt || event.value?.endsAt
  if (!start) return ''
  const day = datePart(start)
  const from = timePart(start)
  const to = end ? timePart(end) : ''
  return to ? `${day} · ${from} – ${to} SGT` : `${day} · ${from} SGT`
})

const venue = computed(() => {
  const name = event.value?.venueName
  const location = event.value?.venueLocation
  if (name && location) return `${name} · ${location}`
  return name || location || 'Venue to be confirmed'
})

const closes = computed(() => {
  const value = event.value?.registrationClosesAt
  if (!value) return 'Not set'
  if (!parseServerTime(value)) return String(value)
  return formatSgt(value)
})

const places = computed(() => {
  if (event.value?.full) return 'Full'
  const count = event.value?.remaining ?? 0
  return count === 1 ? '1 place remaining' : `${count} places remaining`
})

function datePart(value) {
  return formatSgtDate(value)
}

function timePart(value) {
  return formatSgtTime(value)
}

function back() {
  router.push({ path: '/app', query: { tab: 'Browse Events' } })
}

onMounted(async () => {
  try {
    const { data } = await getOpenEvent(route.params.id)
    event.value = data
  } catch {
    // SPM-127: not open for registration, but still public to this attendee when it is
    // confirmed or they registered for it (a notification about it can lead here).
    try {
      const { data } = await getAttendeeCard(route.params.id)
      event.value = data
    } catch (err) {
      error.value = err.response?.data?.detail || 'This event is not open.'
    }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.browse-detail {
  max-width: 760px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}
.back { margin: 0 0 18px -18px; padding-left: 18px; }
.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
}
.page-head { margin-bottom: 18px; }
.eyebrow {
  margin: 0;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}
.page-head h1 {
  margin: 6px 0 8px;
  font-size: 28px;
  font-weight: 500;
  letter-spacing: -.02em;
}
.when { margin: 0; font-size: 14px; color: var(--body); }
.lede {
  margin: 0 0 18px;
  font-size: 15px;
  line-height: 1.6;
  color: var(--text);
}
.lede.muted { color: var(--muted); }
.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: 22px 24px;
}
.facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 24px;
  margin: 0;
}
.facts dt {
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 4px;
}
.facts dd { margin: 0; font-size: 14px; line-height: 1.5; color: var(--body); }
.facts dd.full { color: #FFB4A8; }
@media (max-width: 720px) {
  .browse-detail { padding: 22px 18px 36px; }
  .back { margin-left: 0; }
  .facts { grid-template-columns: 1fr; }
}
</style>
