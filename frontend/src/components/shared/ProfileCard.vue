<template>
  <div class="profile-card" data-testid="profile-card">
    <p v-if="loading" class="note">Loading your profile…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else>
      <h3>{{ profile.userName }}</h3>
      <dl class="facts">
        <div>
          <dt>Email</dt>
          <dd>{{ profile.email }}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{{ roleLabel }}</dd>
        </div>
        <div v-if="profile.organisationId">
          <dt>Organisation</dt>
          <dd>{{ organisationName }}</dd>
        </div>
      </dl>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getMe, getOrganisations } from '../../api/userService.js'
import { roles } from '../../config/roles.js'
import { session } from '../../store/session.js'

// Only reuse the cache for the same signed-in user.
const hit = cached && cached.userId === session.userId ? cached : null
const profile = ref(hit?.profile ?? null)
const organisationName = ref(hit?.organisationName ?? '')
const loading = ref(!hit)
const error = ref('')

const roleLabel = computed(() => roles[profile.value?.role]?.label || profile.value?.role || '')

async function load() {
  error.value = ''
  try {
    const { data } = await getMe()
    profile.value = data
    let orgName = data.organisationId || ''
    if (data.organisationId) {
      try {
        const { data: organisations } = await getOrganisations()
        const match = organisations.find((item) => item.organisationId === data.organisationId)
        if (match?.name) orgName = match.name
      } catch {
        // Falls back to the organisation id.
      }
    }
    organisationName.value = orgName
    cached = { userId: session.userId, profile: data, organisationName: orgName }
  } catch (err) {
    // A card we already have is better than an error on a refresh.
    if (!profile.value) error.value = err.response?.data?.detail || 'Could not load your profile. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<script>
// Shown instantly on re-open, then refreshed. Module-level so it survives the menu closing.
let cached = null
</script>

<style scoped>
.profile-card { padding: var(--space-3); }
h3 { margin: 0 0 var(--space-3); font-size: var(--fs-lg); font-weight: 500; }
.facts { display: grid; gap: var(--space-3); margin: 0; }
dt { margin-bottom: 2px; font-size: var(--fs-xs); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
dd { margin: 0; font-size: var(--fs-sm); color: var(--body); overflow-wrap: anywhere; }
.note { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.error { margin: 0; font-size: var(--fs-sm); color: var(--danger); }
</style>
