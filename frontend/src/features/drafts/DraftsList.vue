<template>
  <div class="drafts">
    <p v-if="loading" class="empty-note">Loading your drafts…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!drafts.length" class="empty-note">No drafts saved yet.</p>

    <template v-else>
      <label class="search">
        Search
        <input v-model="query" type="search" placeholder="Draft name" data-testid="draft-search" />
      </label>
      <p v-if="!visible.length" class="empty-note">No drafts match this search.</p>
      <div v-else class="list">
        <article v-for="draft in visible" :key="draft.eventId" class="draft-card">
          <div class="draft-top">
            <h3 class="draft-name">{{ draft.eventName || 'Untitled event' }}</h3>
            <span class="draft-pill">Draft</span>
          </div>
          <dl class="draft-facts">
            <div>
              <dt>When</dt>
              <dd>{{ formatRange(draft.proposedStartAt, draft.proposedEndAt) }}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{{ draft.category || '—' }}</dd>
            </div>
            <div class="wide">
              <dt>Location</dt>
              <dd>{{ draft.preferredLocation || '—' }}</dd>
            </div>
          </dl>
          <button class="btn btn-outline" @click="edit(draft.eventId)">Edit</button>
        </article>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getMyDrafts } from '../../api/eventService.js'
import { editDraft } from '../../store/draftEditor.js'
import { formatSgtRange } from '../../utils/datetime.js'

const emit = defineEmits(['edit-draft'])

const drafts = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')

const visible = computed(() => {
  const term = query.value.trim().toLowerCase()
  if (!term) return drafts.value
  return drafts.value.filter((draft) => (draft.eventName || '').toLowerCase().includes(term))
})

function formatRange(start, end) {
  if (!start && !end) return 'No date set yet'
  if (!start || !end) return 'Date incomplete'
  return formatSgtRange(start, end)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getMyDrafts()
    drafts.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load your drafts. Please try again.'
  } finally {
    loading.value = false
  }
}

function edit(eventId) {
  editDraft(eventId)
  emit('edit-draft')
}

onMounted(load)
</script>

<style scoped>
.drafts { display: flex; flex-direction: column; gap: 16px; width: 100%; }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; }
.form-error {
  color: #FF8A76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: var(--radius);
  padding: 11px 14px;
}

.search {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 560px;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.search input {
  background: rgba(255, 255, 255, .04);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  color: var(--text);
  font: inherit;
  font-size: 14px;
  letter-spacing: 0;
  text-transform: none;
  padding: 9px 12px;
  width: 100%;
  color-scheme: dark;
}
.search input:focus {
  outline: none;
  border-color: rgba(167, 139, 250, .5);
}

.list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
  gap: 14px;
}
.draft-card {
  display: grid;
  grid-template-columns: minmax(200px, 0.9fr) minmax(0, 2fr) auto;
  align-items: center;
  gap: 12px 28px;
  background: var(--glass);
  border: 1px dashed var(--hairline);
  border-radius: var(--radius);
  padding: 18px 20px;
  transition: border-color .4s var(--ease-out), background .4s var(--ease-out);
}
.draft-card:hover { border-color: rgba(167, 139, 250, .3); background: var(--glass-strong); }
.draft-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.draft-name {
  margin: 0;
  font-family: var(--font);
  font-weight: 500;
  color: var(--text);
  font-size: 18px;
  line-height: 1.3;
}
.draft-facts {
  margin: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(110px, 0.7fr) minmax(110px, 0.8fr);
  gap: 8px 24px;
}
.draft-facts .wide { grid-column: auto; }
.draft-facts dt {
  margin: 0 0 2px;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
}
.draft-facts dd { margin: 0; font-size: 14px; line-height: 1.4; color: var(--body); }
.draft-card .btn { justify-self: end; }

/* Deliberately distinct from the solid purple status pill used for
   submitted requests — dashed and muted, to read as "not sent yet". */
.draft-pill {
  flex-shrink: 0;
  display: inline-block;
  font-size: 11px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  background: transparent;
  border: 1px dashed var(--hairline);
  border-radius: 999px;
  padding: 3px 10px;
}

@media (max-width: 980px) {
  .list,
  .draft-card,
  .draft-facts { grid-template-columns: 1fr; }
  .draft-facts .wide { grid-column: auto; }
  .draft-card .btn { justify-self: start; }
}
</style>
