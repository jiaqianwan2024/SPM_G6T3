<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" data-testid="reject-dialog">
      <h3>Reject this request?</h3>
      <p class="sub">{{ event.eventName }}</p>

      <p class="body">
        Rejecting is final. Any venue or equipment held for the event is released, and the organiser is told
        why. They can submit a new request afterwards.
      </p>

      <label for="reject-reason">Reason</label>
      <select id="reject-reason" v-model="reason" data-testid="reject-reason">
        <option value="" disabled>Choose a reason</option>
        <option v-for="item in REJECTION_REASONS" :key="item" :value="item">{{ item }}</option>
      </select>

      <label for="reject-explanation">Explanation for the organiser</label>
      <textarea
        id="reject-explanation"
        v-model="explanation"
        rows="3"
        maxlength="2000"
        placeholder="Let the organiser know why"
        data-testid="reject-explanation"
      ></textarea>

      <p v-if="error" class="form-error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="btn btn-outline" @click="emit('close')">Cancel</button>
        <button
          type="button"
          class="btn btn-solid"
          :disabled="saving || !reason || !explanation.trim()"
          data-testid="reject-confirm"
          @click="submit"
        >
          {{ saving ? 'Rejecting…' : 'Reject request' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { rejectEvent } from '../../api/eventService.js'
import { REJECTION_REASONS } from '../../config/eventStatus.js'

const props = defineProps({ event: { type: Object, required: true } })
const emit = defineEmits(['close', 'rejected'])

const reason = ref('')
const explanation = ref('')
const saving = ref(false)
const error = ref('')

async function submit() {
  saving.value = true
  error.value = ''
  try {
    const { data } = await rejectEvent(props.event.eventId, reason.value, explanation.value.trim())
    emit('rejected', data)
  } catch (err) {
    const detail = err.response?.data?.detail
    error.value = (typeof detail === 'string' && detail) || 'Could not reject this request. Please try again.'
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
  width: 440px;
  max-width: 100%;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}
.modal h3 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
.sub { margin: 0 0 14px; font-size: 13px; color: var(--muted); }
.body { margin: 0 0 14px; font-size: 14px; line-height: 1.6; color: var(--body); }

label {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); display: block; margin-bottom: 6px;
}
select,
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
}
select { margin-bottom: 16px; }
textarea { resize: vertical; }
select:focus,
textarea:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .6);
  box-shadow: 0 0 0 3px rgba(124, 77, 255, .16);
}

.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
  margin: 14px 0 0;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.btn:disabled { opacity: .55; cursor: not-allowed; }
</style>
