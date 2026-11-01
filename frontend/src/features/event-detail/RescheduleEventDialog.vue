<template>
  <!-- SPM-87: move the event. Each time the new times change, what the move would do is
       checked first (AC2); nothing is released until it is applied (AC5). -->
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="reschedule-title" data-testid="reschedule-dialog">
      <h3 id="reschedule-title">Reschedule this event</h3>
      <p class="sub">{{ event.eventName }} · now {{ formatSgtRange(event.proposedStartAt, event.proposedEndAt) }}</p>

      <div class="row">
        <div class="col">
          <label for="reschedule-start">New start (SGT)</label>
          <input id="reschedule-start" v-model="start" type="datetime-local" :min="today" data-testid="reschedule-start" />
        </div>
        <div class="col">
          <label for="reschedule-end">New end (SGT)</label>
          <input id="reschedule-end" v-model="end" type="datetime-local" :min="laterInput(today, start)" data-testid="reschedule-end" />
        </div>
      </div>

      <section class="impact" data-testid="reschedule-impact" aria-live="polite">
        <p v-if="!start || !end" class="muted">Pick the new date and time to see what the move affects.</p>
        <p v-else-if="checking" class="muted">Checking the venues and equipment at the new time…</p>
        <p v-else-if="previewError" class="form-error">{{ previewError }}</p>
        <template v-else-if="preview">
          <ul class="messages">
            <li v-for="line in preview.messages" :key="line">{{ line }}</li>
          </ul>
          <p v-if="!preview.messages.length" class="muted">Nothing is booked or reserved for this event yet.</p>
        </template>
      </section>

      <!-- AC4: a booked venue that is not free or suitable is named before anything is committed. -->
      <p v-if="unavailable.length" class="warning" data-testid="reschedule-venue-unavailable">
        {{ unavailable.join(', ') }} {{ unavailable.length === 1 ? 'is' : 'are' }} not available at the new time.
        Reschedule anyway to release {{ unavailable.length === 1 ? 'that booking' : 'those bookings' }} and search
        for another venue, or abandon the reschedule. Bookings for venues that are still available stay in place.
      </p>

      <label for="reschedule-reason">Reason</label>
      <textarea
        id="reschedule-reason"
        v-model="reason"
        rows="2"
        maxlength="2000"
        placeholder="Why the event is moving"
        data-testid="reschedule-reason"
      ></textarea>

      <p v-if="error" class="form-error" role="alert" data-testid="reschedule-error">{{ error }}</p>
      <div class="modal-actions">
        <template v-if="unavailable.length">
          <button type="button" class="btn btn-outline" data-testid="reschedule-abandon" @click="emit('close')">
            Abandon
          </button>
          <button
            type="button"
            class="btn btn-solid"
            :disabled="!ready || saving"
            data-testid="reschedule-anyway"
            @click="apply(true)"
          >
            {{ saving ? 'Rescheduling…' : 'Reschedule anyway' }}
          </button>
        </template>
        <template v-else>
          <button type="button" class="btn btn-outline" @click="emit('close')">Keep the current time</button>
          <button type="button" class="btn btn-solid" :disabled="!ready || saving" data-testid="reschedule-submit" @click="apply(false)">
            {{ saving ? 'Rescheduling…' : 'Reschedule' }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { previewReschedule, rescheduleEvent } from '../../api/eventService.js'
import { formatSgtRange, fromSgtInput, laterInput, parseServerTime, sgtMinInput, toSgtInput } from '../../utils/datetime.js'

const props = defineProps({
  event: { type: Object, required: true },
})
const emit = defineEmits(['close', 'rescheduled'])

const today = sgtMinInput()
const start = ref('')
const end = ref('')
const reason = ref('')
const preview = ref(null)
const previewError = ref('')
const checking = ref(false)
const saving = ref(false)
const error = ref('')
// Named by the last preview, or by a 409 when a venue was taken after it.
const unavailable = ref([])

const duration = (() => {
  const from = parseServerTime(props.event.proposedStartAt)
  const to = parseServerTime(props.event.proposedEndAt)
  return from && to ? to.getTime() - from.getTime() : 2 * 60 * 60 * 1000
})()

const ready = computed(() => !!preview.value && !checking.value && !!reason.value.trim())

// A new start keeps the event's length unless an end after it is already chosen.
watch(start, (value) => {
  if (!value || (end.value && end.value > value)) return
  end.value = toSgtInput(new Date(new Date(`${value}:00+08:00`).getTime() + duration).toISOString())
})

let timer = null
watch([start, end], () => {
  clearTimeout(timer)
  preview.value = null
  previewError.value = ''
  unavailable.value = []
  if (!start.value || !end.value) return
  timer = setTimeout(check, 400)
})
onUnmounted(() => clearTimeout(timer))

function message(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  return detail?.message || fallback
}

async function check() {
  checking.value = true
  try {
    const { data } = await previewReschedule(props.event.eventId, fromSgtInput(start.value), fromSgtInput(end.value))
    preview.value = data
    unavailable.value = data.unavailableVenues || []
  } catch (err) {
    previewError.value = message(err, 'The new time could not be checked. Please try again.')
  } finally {
    checking.value = false
  }
}

async function apply(confirmVenueUnavailable) {
  saving.value = true
  error.value = ''
  try {
    const { data } = await rescheduleEvent(props.event.eventId, {
      proposedStartAt: fromSgtInput(start.value),
      proposedEndAt: fromSgtInput(end.value),
      reason: reason.value.trim(),
      confirmVenueUnavailable,
    })
    emit('rescheduled', data)
  } catch (err) {
    const detail = err.response?.data?.detail
    if (detail?.requiresConfirmation) unavailable.value = detail.unavailableVenues.map((venue) => venue.venueName)
    error.value = message(err, 'The event was not rescheduled. Please try again.')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(5, 2, 14, .7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center; z-index: 20;
  padding: 16px;
}
.modal {
  background: linear-gradient(160deg, #1A0C3B, #0D0524);
  border: 1px solid rgba(167, 139, 250, .28);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
  border-radius: var(--radius);
  padding: 30px;
  width: 520px;
  max-width: 100%;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}
.modal h3 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
.sub { margin: 0 0 16px; font-size: 13px; color: var(--muted); }
label {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); display: block; margin: 0 0 6px;
}
.row { display: flex; gap: 12px; }
.col { flex: 1; min-width: 0; }
input, textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: var(--radius);
  padding: 10px 12px;
  font-size: 14px;
  color: var(--text);
  font-family: var(--font);
  margin: 0 0 14px;
}
textarea { line-height: 1.6; resize: vertical; }
input:focus, textarea:focus { outline: none; border-color: rgba(167, 139, 250, .6); }
.impact {
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: 12px 14px;
  margin: 0 0 14px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--body);
}
.messages { margin: 0; padding-left: 18px; }
.muted { margin: 0; color: var(--muted); }
.warning {
  margin: 0 0 14px;
  padding: 11px 14px;
  border-radius: var(--radius);
  border: 1px solid rgba(255, 211, 138, .35);
  background: rgba(255, 211, 138, .08);
  color: #ffd38a;
  font-size: 13px;
  line-height: 1.6;
}
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
  margin: 0 0 14px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 6px; }
@media (max-width: 560px) {
  .row { flex-direction: column; gap: 0; }
}
</style>
