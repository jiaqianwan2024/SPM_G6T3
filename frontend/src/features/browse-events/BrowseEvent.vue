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

      <!-- SPM-11: register, or see the registration already held (AC1, AC4). -->
      <section v-if="mine" class="panel register" data-testid="existing-registration">
        <p class="register-done" data-testid="register-confirmation">
          You are registered for <strong>{{ event.eventName }}</strong><template v-if="schedule">, {{ schedule }}</template>,
          at {{ venue }}.
        </p>
        <p class="muted">
          Registered as {{ mine.attendeeName }} ({{ mine.attendeeEmail }}).
          <RouterLink :to="`/app/registrations/${mine.attendeeRegistrationId}`">View or withdraw</RouterLink>
        </p>
      </section>
      <p v-else-if="event.full" class="panel notice" data-testid="event-full">
        This event is full, so registration is unavailable. A place may open up if someone withdraws.
      </p>
      <section v-else-if="openForRegistration" class="panel register">
        <button v-if="!registering" type="button" class="btn btn-solid" data-testid="event-register" @click="registering = true">
          Register
        </button>
        <form v-else class="register-form" novalidate @submit.prevent="submit">
          <label for="register-name">Name <span class="req">*</span></label>
          <input id="register-name" v-model.trim="form.name" autocomplete="name" data-testid="register-name" />
          <p v-if="attempted && !form.name" class="field-error" data-testid="register-name-error">Enter your name.</p>
          <label for="register-email">Email <span class="req">*</span></label>
          <!-- An attendee registers only themselves, so the email is their account's (enforced on the server too). -->
          <input id="register-email" :value="form.email" type="email" readonly data-testid="register-email" />
          <p class="field-hint" data-testid="register-email-hint">You can only register yourself, with your account's email.</p>
          <p v-if="submitError" class="form-error" data-testid="register-error">{{ submitError }}</p>
          <div class="actions">
            <button type="submit" class="btn btn-solid" :disabled="saving" data-testid="register-submit">
              {{ saving ? 'Registering…' : 'Register' }}
            </button>
          </div>
        </form>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAttendeeCard, getOpenEvent } from '../../api/eventService.js'
import { getMyRegistrations, registerForEvent } from '../../api/registrationService.js'
import { formatSgt, formatSgtDate, formatSgtTime, parseServerTime } from '../../utils/datetime.js'
import { session } from '../../store/session.js'

const route = useRoute()
const router = useRouter()
const event = ref(null)
const loading = ref(true)
const error = ref('')
// Only an event read from the open-for-registration list can be registered for.
const openForRegistration = ref(false)
const mine = ref(null)
// The list's Register button opens the form straight away.
const registering = ref(route.query.register === '1')
// The attendee registers themselves: the name starts as their account's and can be edited
// (SPM-11 AC2), and the email is always their account's.
const form = reactive({ name: session.name || '', email: session.email || '' })
const attempted = ref(false)
const saving = ref(false)
const submitError = ref('')

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

async function loadMine() {
  try {
    const { data } = await getMyRegistrations()
    mine.value = data.find((row) => row.eventId === route.params.id && row.status === 'registered') || null
  } catch {
    mine.value = null
  }
}

async function submit() {
  attempted.value = true
  submitError.value = ''
  if (!form.name) return
  saving.value = true
  try {
    const { data } = await registerForEvent(route.params.id, form.name, form.email)
    mine.value = data
    // AC4: the places left drop at once.
    const { data: fresh } = await getOpenEvent(route.params.id).catch(() => ({ data: event.value }))
    event.value = fresh
  } catch (err) {
    const detail = err.response?.data?.detail
    submitError.value = typeof detail === 'string' ? detail : 'Your registration could not be saved. Please try again.'
    // AC6 and AC8: someone else took the last place meanwhile.
    if (/full|capacity/i.test(submitError.value)) event.value = { ...event.value, full: true, remaining: 0 }
    if (/already registered/i.test(submitError.value)) await loadMine()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  loadMine()
  try {
    const { data } = await getOpenEvent(route.params.id)
    event.value = data
    openForRegistration.value = true
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
.register { margin-top: 16px; }
.register-done { margin: 0 0 6px; font-size: 15px; color: var(--text); }
.muted { margin: 0; font-size: 13px; color: var(--muted); }
.notice { margin: 16px 0 0; font-size: 14px; color: #FFB4A8; }
.register-form { display: grid; gap: 6px; }
.register-form label { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin-top: 8px; }
.register-form input {
  background: transparent;
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  color: var(--text);
  padding: 9px 12px;
  font-size: 14px;
}
.register-form input[readonly] { color: var(--muted); cursor: default; }
.req { color: var(--iris-soft); }
.field-error { margin: 0; font-size: 12px; color: #FF8A76; }
.field-hint { margin: 0; font-size: 12px; color: var(--muted); }
.register-form .actions { display: flex; margin-top: 12px; }
@media (max-width: 720px) {
  .browse-detail { padding: 22px 18px 36px; }
  .back { margin-left: 0; }
  .facts { grid-template-columns: 1fr; }
}
</style>

