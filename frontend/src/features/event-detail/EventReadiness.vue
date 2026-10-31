<template>
  <div class="readiness">
    <button type="button" class="btn btn-ghost back" @click="router.push(`/app/events/${route.params.id}`)">← Event</button>
    <header class="page-head">
      <div>
        <p class="eyebrow">Follow-up</p>
        <h1>Readiness</h1>
        <p class="lede">Venue, equipment, and anything else still waiting on someone.</p>
      </div>
    </header>

    <p v-if="reverifyNote" class="notice attention" data-testid="readiness-reverify">{{ reverifyNote }}</p>
    <p v-if="loading" class="empty-note">Loading readiness…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <template v-else>
      <form v-if="canWrite" class="panel line-form" data-testid="readiness-create-form" @submit.prevent="createLine">
        <h2>Add a follow-up line</h2>
        <div class="fields">
          <label>
            Category
            <input v-model="draft.category" required placeholder="venue, equipment, registration…" data-testid="readiness-create-category" />
          </label>
          <label>
            Personnel
            <select v-model="draft.handlerId" required data-testid="readiness-create-handler">
              <option value="" disabled>Choose someone</option>
              <option v-for="person in people" :key="person.userId" :value="person.userId">
                {{ person.userName }} · {{ person.email }}
              </option>
            </select>
          </label>
          <label>
            Status
            <select v-model="draft.status" data-testid="readiness-create-status">
              <option v-for="status in STATUSES" :key="status" :value="status">{{ statusLabel(status) }}</option>
            </select>
          </label>
          <label>
            Due (SGT)
            <input v-model="draft.dueAt" type="datetime-local" :min="sgtMinInput()" data-testid="readiness-create-due" />
          </label>
          <label class="wide">
            Note
            <input v-model="draft.note" data-testid="readiness-create-note" />
          </label>
          <label>
            Attachment name
            <input v-model="draft.attachmentName" data-testid="readiness-create-attachment-name" />
          </label>
          <label>
            Attachment link
            <input v-model="draft.attachmentUrl" type="url" placeholder="https://" data-testid="readiness-create-attachment-url" />
          </label>
        </div>
        <p v-if="formError && !editingId" class="form-error">{{ formError }}</p>
        <button type="submit" class="btn btn-solid" :disabled="saving">{{ saving && !editingId ? 'Saving…' : 'Add line' }}</button>
      </form>

      <p v-if="!rows.length" class="empty-note">No follow-up lines yet.</p>

      <div v-else class="sheet">
        <div class="columns" aria-hidden="true">
          <span>Category</span>
          <span>Personnel</span>
          <span>Contact</span>
          <span>Status</span>
          <span>Assigned</span>
          <span>Attachments</span>
        </div>

        <article
          v-for="row in rows"
          :key="row.itemId"
          class="event-card"
          :class="{ late: row.overdue, soon: row.dueSoon }"
          data-testid="readiness-row"
        >
          <div class="facts">
            <div>
              <span class="label">Category</span>
              <span data-testid="readiness-category">{{ row.category }}</span>
            </div>
            <div>
              <span class="label">Personnel</span>
              <span data-testid="readiness-handler">{{ handlerLabel(row) }}</span>
            </div>
            <div>
              <span class="label">Contact</span>
              <span data-testid="readiness-handler-contact">{{ contactOf(row) || 'No contact' }}</span>
            </div>
            <div class="status-cell">
              <span class="label">Status</span>
              <div class="status-flags">
                <span class="status-pill" data-testid="readiness-status">{{ statusLabel(row.status) }}</span>
                <span v-if="row.overdue" class="flag late" data-testid="readiness-overdue">Overdue</span>
                <span v-if="row.dueSoon" class="flag soon" data-testid="readiness-due-soon">Due soon</span>
              </div>
              <button
                v-if="canWrite"
                type="button"
                class="btn btn-outline status-action"
                data-testid="readiness-confirm-status"
                @click="askStatus(row)"
              >
                Confirm
              </button>
            </div>
            <div>
              <span class="label">Assigned</span>
              <span data-testid="readiness-assigned-at">{{ formatSgt(row.assignedAt) }}</span>
            </div>
            <div data-testid="readiness-attachments">
              <span class="label">Attachments</span>
              <a
                v-for="file in row.attachments"
                :key="file.url"
                data-testid="readiness-attachment-link"
                :href="file.url"
              >{{ file.name || file.url }}</a>
              <span v-if="!row.attachments.length" class="muted">No attachments</span>
            </div>
          </div>
          <p v-if="row.note" class="note" data-testid="readiness-note">{{ row.note }}</p>

          <div v-if="canWrite" class="row-actions">
            <button type="button" class="btn btn-ghost icon-btn" data-testid="readiness-edit" aria-label="Edit" @click="startEdit(row)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
              </svg>
            </button>
            <button type="button" class="btn btn-ghost icon-btn danger" data-testid="readiness-delete" aria-label="Delete" @click="askDelete(row)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path d="M4 7h16" />
                <path d="M9 7V5h6v2" />
                <path d="M18 7l-1 13H7L6 7" />
                <path d="M10 11v6M14 11v6" />
              </svg>
            </button>
          </div>

        <form v-if="editingId === row.itemId" class="edit-form" data-testid="readiness-edit-form" @submit.prevent="saveEdit(row)">
          <label>
            Category
            <input v-model="edit.category" required data-testid="readiness-edit-category" />
          </label>
          <label>
            Personnel
            <select v-model="edit.handlerId" required data-testid="readiness-edit-handler">
              <option v-if="edit.handlerId && !knownHandler(edit.handlerId)" :value="edit.handlerId">
                {{ handlerLabel(row) }}
              </option>
              <option v-for="person in people" :key="person.userId" :value="person.userId">
                {{ person.userName }} · {{ person.email }}
              </option>
            </select>
          </label>
          <label>
            Status
            <select v-model="edit.status" data-testid="readiness-edit-status">
              <option v-for="status in statusChoices(edit.status)" :key="status" :value="status">{{ statusLabel(status) }}</option>
            </select>
          </label>
          <label>
            Note
            <input v-model="edit.note" data-testid="readiness-edit-note" />
          </label>
          <label>
            Due (SGT)
            <input v-model="edit.dueAt" type="datetime-local" :min="sgtMinInput(toLocalInput(row.dueAt))" data-testid="readiness-edit-due" />
          </label>
          <label>
            Attachment name
            <input v-model="edit.attachmentName" data-testid="readiness-edit-attachment-name" />
          </label>
          <label>
            Attachment link
            <input v-model="edit.attachmentUrl" type="url" data-testid="readiness-edit-attachment-url" />
          </label>
          <p v-if="formError" class="form-error">{{ formError }}</p>
          <div class="row-actions">
            <button type="button" class="btn btn-ghost" @click="editingId = ''">Cancel</button>
            <button type="submit" class="btn btn-solid" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
          </div>
        </form>
        </article>
      </div>
    </template>

    <div v-if="pending" class="modal-backdrop" @click.self="closeStatus">
      <div class="modal" data-testid="readiness-confirm-dialog" role="dialog">
        <h3>Update status</h3>
        <p>Mark this {{ pending.category }} line as {{ statusLabel(pendingBody?.status || 'confirmed') }}?</p>
        <p v-if="actionError" class="form-error">{{ actionError }}</p>
        <div class="modal-actions">
          <button type="button" class="btn btn-outline" :disabled="saving" @click="closeStatus">Cancel</button>
          <button type="button" class="btn btn-solid" :disabled="saving" @click="confirm">Confirm</button>
        </div>
      </div>
    </div>

    <div v-if="removing" class="modal-backdrop" @click.self="closeDelete">
      <div class="modal" data-testid="readiness-delete-dialog" role="dialog">
        <h3>Delete this line?</h3>
        <p>The {{ removing.category }} follow-up will be removed.</p>
        <p v-if="actionError" class="form-error">{{ actionError }}</p>
        <div class="modal-actions">
          <button type="button" class="btn btn-outline" :disabled="saving" @click="closeDelete">Cancel</button>
          <button type="button" class="btn btn-solid" :disabled="saving" @click="remove">Delete line</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createReadinessItem, deleteReadinessItem, getReadiness, updateReadinessItem } from '../../api/eventService.js'
import { getEventReservations } from '../../api/equipmentService.js'
import { getUsers } from '../../api/userService.js'
import { getVenueBookings } from '../../api/venueService.js'
import { session } from '../../store/session.js'
import { formatSgt, fromSgtInput, sgtMinInput, toSgtInput } from '../../utils/datetime.js'

const STATUSES = ['outstanding', 'in_progress', 'confirmed']

const route = useRoute()
const router = useRouter()
const rows = ref([])
const people = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const formError = ref('')
const actionError = ref('')
const pending = ref(null)
const pendingBody = ref(null)
const removing = ref(null)
const editingId = ref('')
const edit = reactive(blankLine())
const draft = reactive(blankLine())

const canWrite = computed(() => session.role === 'coordinator')

function statusLabel(status) {
  return String(status || '').replaceAll('_', ' ')
}

function personFor(row) {
  return people.value.find((person) => person.userId === row.handlerId)
}

function handlerLabel(row) {
  const stored = (row.handlerName || row.personnel || '').trim()
  const person = personFor(row)
  if (person?.userName && (!stored || stored === row.handlerId)) return person.userName
  return stored || person?.userName || 'Unassigned'
}

function blankLine() {
  return {
    category: '',
    handlerId: '',
    status: 'outstanding',
    note: '',
    dueAt: '',
    attachmentName: '',
    attachmentUrl: '',
  }
}

function contactOf(row) {
  return row.handlerEmail || row.handlerPhone || personFor(row)?.email || ''
}

function knownHandler(handlerId) {
  return people.value.some((person) => person.userId === handlerId)
}

function statusChoices(current) {
  return STATUSES.includes(current) ? STATUSES : [current, ...STATUSES]
}

function message(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || 'Invalid value').join(' ')
  return fallback
}

// Due dates are typed and shown in Singapore time, and sent as UTC. A new due date
// starts at today; an existing one that has passed stays allowed when its line is edited.
function toIso(value) {
  return fromSgtInput(value) || null
}

function toLocalInput(value) {
  return toSgtInput(value)
}

function attachmentsFrom(line, existing = []) {
  if (!line.attachmentUrl) return existing
  return [{ name: line.attachmentName || line.attachmentUrl, url: line.attachmentUrl }]
}

const reverifyNote = ref('')

async function loadReverification() {
  const eventId = route.params.id
  try {
    const [bookings, reservations] = await Promise.all([
      getVenueBookings({ eventId }).then((response) => response.data),
      getEventReservations(eventId).then((response) => response.data),
    ])
    const venueFlag = bookings.some((row) => row.needsReverification)
    const equipmentFlag = reservations.some((row) => row.needsReverification)
    if (venueFlag || equipmentFlag) {
      reverifyNote.value = 'A venue booking or equipment reservation needs re-verification before this event is fully ready.'
    }
  } catch {
    reverifyNote.value = ''
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getReadiness(route.params.id)
    rows.value = data
  } catch (err) {
    error.value = message(err, 'Could not load readiness.')
  } finally {
    loading.value = false
  }
}

async function loadPeople() {
  try {
    const { data } = await getUsers()
    people.value = [...data].sort((a, b) => a.userName.localeCompare(b.userName))
  } catch {
    people.value = []
  }
}

function askStatus(row) {
  removing.value = null
  actionError.value = ''
  pendingBody.value = { status: 'confirmed' }
  pending.value = row
}

function closeStatus() {
  pending.value = null
  pendingBody.value = null
  actionError.value = ''
}

function startEdit(row) {
  closeStatus()
  closeDelete()
  formError.value = ''
  editingId.value = row.itemId
  const file = row.attachments?.[0] || {}
  Object.assign(edit, {
    category: row.category,
    handlerId: row.handlerId,
    status: row.status,
    note: row.note || '',
    dueAt: toLocalInput(row.dueAt),
    attachmentName: file.name || '',
    attachmentUrl: file.url || '',
  })
}

function editBody(row) {
  const body = {
    category: edit.category,
    handlerId: edit.handlerId,
    note: edit.note,
    dueAt: toIso(edit.dueAt),
    attachments: attachmentsFrom(edit, row.attachments || []),
  }
  if (edit.status !== row.status) body.status = edit.status
  return body
}

async function saveEdit(row) {
  formError.value = ''
  const body = editBody(row)
  if (body.status) {
    actionError.value = ''
    pendingBody.value = body
    pending.value = row
    return
  }
  saving.value = true
  try {
    await updateReadinessItem(route.params.id, row.itemId, body)
    editingId.value = ''
    await load()
  } catch (err) {
    formError.value = message(err, 'Could not save this line.')
  } finally {
    saving.value = false
  }
}

async function confirm() {
  const row = pending.value
  const body = pendingBody.value || { status: 'confirmed' }
  saving.value = true
  actionError.value = ''
  try {
    await updateReadinessItem(route.params.id, row.itemId, body)
    pending.value = null
    pendingBody.value = null
    editingId.value = ''
    await load()
  } catch (err) {
    actionError.value = message(err, 'Could not update the status.')
  } finally {
    saving.value = false
  }
}

function askDelete(row) {
  closeStatus()
  actionError.value = ''
  removing.value = row
}

function closeDelete() {
  removing.value = null
  actionError.value = ''
}

async function remove() {
  const row = removing.value
  saving.value = true
  actionError.value = ''
  try {
    await deleteReadinessItem(route.params.id, row.itemId)
    if (editingId.value === row.itemId) editingId.value = ''
    removing.value = null
    await load()
  } catch (err) {
    actionError.value = err.response?.status === 404
      ? 'This line comes from the live venue or equipment arrangements, so it stays until those change.'
      : message(err, 'Could not delete this line.')
  } finally {
    saving.value = false
  }
}

async function createLine() {
  formError.value = ''
  saving.value = true
  try {
    await createReadinessItem(route.params.id, {
      category: draft.category,
      handlerId: draft.handlerId,
      status: draft.status,
      note: draft.note,
      dueAt: toIso(draft.dueAt),
      attachments: attachmentsFrom(draft),
    })
    Object.assign(draft, blankLine())
    await load()
  } catch (err) {
    formError.value = message(err, 'Could not add this line.')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load()
  loadPeople()
  loadReverification()
})
</script>

<style scoped>
.readiness {
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}
.back { margin: 0 0 18px -18px; padding-left: 18px; }
.page-head { margin-bottom: 18px; }
.page-head h1 { margin: 6px 0 8px; font-size: 28px; font-weight: 500; letter-spacing: -.02em; }
.lede { margin: 0; color: var(--body); font-size: 14px; }
.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #ff8a76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
}
.panel, .sheet, .event-card {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: var(--radius);
}
.panel { padding: 28px 24px 22px; margin-bottom: 18px; }
.panel h2, .edit-form h2 { margin: 0 0 14px; font-size: 16px; font-weight: 500; color: var(--text); }
.fields, .edit-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; }
.fields .wide { grid-column: 1 / -1; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
input, select {
  font: inherit;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  color: var(--text);
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: 8px 10px;
}
.panel .btn { margin-top: 14px; }
.sheet { overflow: hidden; }
.columns, .facts {
  display: grid;
  grid-template-columns: 1.1fr 1.2fr 1.6fr 1.3fr 1.2fr 1.2fr;
  gap: 12px;
  align-items: start;
}
.columns {
  padding: 12px 18px;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  border-bottom: 1px solid var(--hairline);
}
.event-card { border: none; border-radius: 0; border-top: 1px solid var(--hairline); padding: 14px 18px; }
.event-card:first-of-type { border-top: none; }
.event-card.late { box-shadow: inset 3px 0 0 #ff8a76; }
.event-card.soon { box-shadow: inset 3px 0 0 #38e0c8; }
.event-card.late.soon { box-shadow: inset 3px 0 0 #ff8a76; }
.label { display: none; }
.facts { font-size: 14px; color: var(--text); }
.facts a { display: block; color: var(--iris-soft); }
.muted { color: var(--muted); }
.status-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.status-flags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.status-action { padding: 6px 12px; font-size: 12px; }
.status-pill {
  display: inline-block;
  font-size: 11px;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--halo);
  background: rgba(124, 77, 255, .18);
  border: 1px solid rgba(167, 139, 250, .3);
  border-radius: 999px;
  padding: 3px 10px;
}
.flag {
  display: inline-block;
  margin-left: 0;
  font-size: 11px;
  letter-spacing: .04em;
  text-transform: uppercase;
  border-radius: 999px;
  padding: 3px 8px;
}
.flag.soon { color: #07332c; background: #38e0c8; }
.flag.late { color: #3a120c; background: #ffb4a8; }
.note { margin: 10px 0 0; font-size: 13px; color: var(--body); }
.row-actions { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.row-actions .icon-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}
.row-actions .icon-btn { color: var(--icon); }
.row-actions .icon-btn svg { width: 16px; height: 16px; }
.row-actions .icon-btn.danger:hover { color: #ff8a76; }
.edit-form {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--hairline);
}
.edit-form .row-actions { grid-column: 1 / -1; }
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(5, 2, 14, .7);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: min(420px, calc(100% - 32px));
  background: linear-gradient(160deg, #1a0c3b, #0d0524);
  border: 1px solid rgba(167, 139, 250, .28);
  border-radius: var(--radius);
  padding: 28px;
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7);
}
.modal h3 { margin: 0 0 10px; font-size: 18px; font-weight: 500; }
.modal p { margin: 0 0 8px; font-size: 14px; line-height: 1.6; color: var(--body); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.btn:disabled { opacity: .55; cursor: progress; }

@media (max-width: 900px) {
  .readiness { padding: 22px 18px 36px; }
  .back { margin-left: 0; }
  .columns { display: none; }
  .fields, .edit-form, .facts { grid-template-columns: 1fr; }
  .label { display: block; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin-bottom: 2px; }
}
</style>
