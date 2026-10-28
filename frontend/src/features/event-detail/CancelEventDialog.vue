<template>
  <!-- SPM-88 AC3: confirm, with what will be released and who will be told. -->
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="cancel-title" data-testid="cancel-confirm">
      <h3 id="cancel-title">Cancel this event?</h3>
      <p class="sub">{{ event.eventName }}</p>

      <p class="body">Cancelling takes effect immediately and cannot be undone.</p>

      <p class="heading">Released now</p>
      <ul data-testid="cancel-releases">
        <li>{{ venueLine }}</li>
        <li>Every equipment reservation for the event</li>
        <li v-if="event.registrationEnabled">Registration, which closes</li>
      </ul>

      <p class="heading">Told, with your reason</p>
      <ul data-testid="cancel-notified">
        <li v-for="line in notified" :key="line">{{ line }}</li>
      </ul>

      <label for="cancel-reason">Reason</label>
      <textarea
        id="cancel-reason"
        v-model="reason"
        rows="3"
        maxlength="2000"
        placeholder="Why the event is cancelled"
        data-testid="cancel-reason"
      ></textarea>

      <p v-if="error" class="form-error" role="alert" data-testid="cancel-error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="btn btn-outline" @click="emit('close')">Keep event</button>
        <button
          type="button"
          class="btn btn-danger"
          :disabled="saving || !reason.trim()"
          data-testid="cancel-submit"
          @click="submit"
        >
          {{ saving ? 'Cancelling…' : 'Cancel event' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { cancelEvent } from '../../api/eventService.js'
import { session } from '../../store/session.js'

const props = defineProps({
  event: { type: Object, required: true },
  venueName: { type: String, default: '' }
})
const emit = defineEmits(['close', 'cancelled'])

const reason = ref('')
const saving = ref(false)
const error = ref('')

const venueLine = computed(() =>
  props.venueName
    ? `The booking at ${props.venueName}, and any pending venue requests`
    : 'Any venue bookings and pending venue requests'
)

const notified = computed(() => {
  const count = props.event.registeredCount || 0
  const lines = []
  if (count) lines.push(`${count} registered attendee${count === 1 ? '' : 's'}`)
  if (session.role === 'coordinator') lines.push('The organiser')
  else if (props.event.coordinatorId) lines.push('The assigned coordinator')
  lines.push('The Venue Staff who approved its venue booking')
  lines.push('The Technical Support staff holding its equipment')
  return lines
})

async function submit() {
  saving.value = true
  error.value = ''
  try {
    const { data } = await cancelEvent(props.event.eventId, reason.value.trim())
    emit('cancelled', data)
  } catch (err) {
    // AC9: a failed release leaves the event as it was; say so.
    const detail = err.response?.data?.detail
    error.value = (typeof detail === 'string' && detail) || 'The event was not cancelled. Please try again.'
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
  width: 460px;
  max-width: 100%;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}
.modal h3 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
.sub { margin: 0 0 14px; font-size: 13px; color: var(--muted); }
.body { margin: 0 0 14px; font-size: 14px; line-height: 1.6; color: var(--body); }
.heading, label {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); display: block; margin: 0 0 6px;
}
ul { margin: 0 0 16px; padding-left: 18px; font-size: 14px; line-height: 1.6; color: var(--body); }
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: var(--radius);
  padding: 11px 12px;
  font-size: 14px;
  color: var(--text);
  font-family: var(--font);
  line-height: 1.6;
  resize: vertical;
}
textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}
.form-error { margin: 12px 0 0; font-size: 13px; color: #ffb4b4; line-height: 1.5; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.btn-danger { color: #fff; background: #b91c1c; border: 1px solid #b91c1c; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
</style>
