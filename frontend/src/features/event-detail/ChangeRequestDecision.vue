<template>
  <!-- SPM-106 AC7 / SPM-85 AC6 to AC8: the assigned coordinator accepts or declines a pending change request. -->
  <div class="decision" data-testid="change-request-decision">
    <label :for="reasonId">Reason for the organiser</label>
    <textarea
      :id="reasonId"
      v-model="reason"
      rows="2"
      maxlength="2000"
      placeholder="Required to decline; optional to accept"
      data-testid="change-request-decision-reason"
    ></textarea>
    <!-- AC8: a request is never partly applied; part of it is agreed by asking for a narrower one. -->
    <label class="pick">
      <input v-model="askNarrower" type="checkbox" data-testid="change-request-ask-narrower" @change="acceptWarning = null" />
      Only part of this can go ahead: decline it and ask the organiser for a narrower request
    </label>
    <div v-if="acceptWarning" class="warning" data-testid="change-request-accept-warning">
      <p>{{ acceptWarning.message }}</p>
      <ul v-if="acceptWarning.arrangements?.length">
        <li v-for="arrangement in acceptWarning.arrangements" :key="arrangement.id">{{ arrangement.summary }}</li>
      </ul>
    </div>
    <div class="form-actions">
      <button
        type="button"
        class="btn btn-outline small"
        :disabled="busy || !reason.trim()"
        data-testid="change-request-decline"
        @click="decline"
      >
        {{ askNarrower ? 'Decline and ask for a narrower request' : 'Decline' }}
      </button>
      <button
        v-if="!acceptWarning"
        type="button"
        class="btn btn-solid small"
        :disabled="busy || askNarrower"
        data-testid="change-request-accept"
        @click="accept(false)"
      >
        Accept and apply
      </button>
      <button
        v-else
        type="button"
        class="btn btn-solid small"
        :disabled="busy"
        data-testid="change-request-accept-confirm"
        @click="accept(true)"
      >
        Apply anyway
      </button>
    </div>
    <p v-if="error" class="form-error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { acceptChangeRequest, declineChangeRequest } from '../../api/eventService.js'
import { uid } from '../../composables/uid.js'
import { errorText } from './changeRequestValues.js'

const props = defineProps({
  eventId: { type: String, required: true },
  changeRequestId: { type: String, required: true },
})
// 'accepted' or 'declined', once the server has recorded it.
const emit = defineEmits(['decided'])

const reasonId = uid('change-decision-reason')
const reason = ref('')
const askNarrower = ref(false)
const acceptWarning = ref(null)
const busy = ref(false)
const error = ref('')

async function act(action, outcome, fallback) {
  busy.value = true
  error.value = ''
  try {
    await action()
    acceptWarning.value = null
    reason.value = ''
    askNarrower.value = false
    emit('decided', outcome)
  } catch (err) {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409 && detail?.requiresConfirmation) {
      acceptWarning.value = detail
    } else {
      error.value = errorText(err, fallback)
    }
  } finally {
    busy.value = false
  }
}

function decline() {
  return act(
    () => declineChangeRequest(props.eventId, props.changeRequestId, reason.value, askNarrower.value),
    'declined',
    'Could not decline the request.',
  )
}

function accept(confirm) {
  return act(
    () => acceptChangeRequest(props.eventId, props.changeRequestId, reason.value, confirm),
    'accepted',
    'Could not accept the request.',
  )
}
</script>

<style scoped>
.decision { border-top: 1px solid var(--hairline); padding-top: 12px; margin-top: 4px; }
label {
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 6px;
}
.pick { display: flex; align-items: flex-start; gap: 8px; font-size: 13px; text-transform: none; letter-spacing: 0; color: var(--body); margin: 0 0 12px; line-height: 1.5; }
.pick input { margin-top: 3px; }
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--hairline);
  background: rgba(255, 255, 255, .03);
  border-radius: var(--radius);
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 14px;
  color: var(--text);
  font-family: var(--font);
  resize: vertical;
  line-height: 1.5;
}
textarea:focus { outline: none; border-color: rgba(167, 139, 250, .6); box-shadow: 0 0 0 3px rgba(124, 77, 255, .16); }
.warning {
  font-size: 13px;
  line-height: 1.6;
  color: #FFD9A8;
  background: rgba(255, 170, 80, .08);
  border: 1px solid rgba(255, 196, 120, .3);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin-bottom: 12px;
}
.warning p, .warning ul { margin: 0; }
.form-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
.btn.small { padding: 7px 14px; font-size: 13px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
  margin: 8px 0 0;
}
</style>
