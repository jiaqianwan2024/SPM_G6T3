<template>
  <div class="profile-card" data-testid="profile-card">
    <p v-if="loading" class="note">Loading your profile…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else>
      <h3>{{ profile.userName }}</h3>
      <ul class="facts">
        <li>
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <!-- one person over three, joined by a reporting line -->
            <circle cx="12" cy="4.2" r="2.2" />
            <path d="M8 10.2c.3-2 1.9-3.2 4-3.2s3.7 1.2 4 3.2" />
            <path d="M12 10.2v2.2M5 14.4v-2h14v2" />
            <circle cx="5" cy="16.4" r="1.7" />
            <circle cx="12" cy="16.4" r="1.7" />
            <circle cx="19" cy="16.4" r="1.7" />
            <path d="M2.2 22c.3-1.8 1.4-2.8 2.8-2.8s2.5 1 2.8 2.8" />
            <path d="M9.2 22c.3-1.8 1.4-2.8 2.8-2.8s2.5 1 2.8 2.8" />
            <path d="M16.2 22c.3-1.8 1.4-2.8 2.8-2.8s2.5 1 2.8 2.8" />
          </svg>
          <span class="sr-only">Role: </span>
          <span class="detail">{{ roleLabel }}</span>
        </li>
        <li>
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3.5" y="5.5" width="17" height="13" rx="2.5" />
            <path d="m4.5 7.5 7.5 5.5 7.5-5.5" />
          </svg>
          <span class="sr-only">Email: </span>
          <span class="detail">{{ profile.email }}</span>
        </li>
        <li v-if="profile.organisationId">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 20.5V6.5a1.5 1.5 0 0 1 1.5-1.5h6A1.5 1.5 0 0 1 14 6.5v14" />
            <path d="M14 10.5h3.5A1.5 1.5 0 0 1 19 12v8.5M3.5 20.5h17" />
            <path d="M8.5 9h2M8.5 12.5h2M8.5 16h2" />
          </svg>
          <span class="sr-only">Organisation: </span>
          <span class="detail">{{ organisationName }}</span>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getMe, getOrganisations } from '../../api/userService.js'
import { roles } from '../../config/roles.js'
import { session } from '../../store/session.js'

// `sample` renders fixed data without calling the API (the /dev/ui catalogue). Otherwise the card
// loads the signed-in user, reusing the last result for the same user while it refreshes.
const props = defineProps({ sample: { type: Object, default: null } })

const hit = !props.sample && cached && cached.userId === session.userId ? cached : null
const profile = ref(props.sample ?? hit?.profile ?? null)
const organisationName = ref(props.sample?.organisationName ?? hit?.organisationName ?? '')
const loading = ref(!props.sample && !hit)
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

onMounted(() => { if (!props.sample) load() })
</script>

<script>
// Shown instantly on re-open, then refreshed. Module-level so it survives the menu closing.
let cached = null
</script>

<style scoped>
.profile-card { padding: var(--space-3); }
h3 { margin: 0 0 var(--space-3); font-size: var(--fs-lg); font-weight: 500; overflow-wrap: anywhere; }
.facts { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.facts li { display: flex; align-items: flex-start; gap: var(--space-3); min-width: 0; }
.icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  fill: none;
  stroke: var(--icon);
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
/* line-height matches the 20px icon, so the icon stays beside the first line when the text wraps */
.detail { min-width: 0; font-size: var(--fs-sm); line-height: 20px; color: var(--body); overflow-wrap: anywhere; }
/* Visible to screen readers only: the icon stands in for the label on screen. */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.note { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.error { margin: 0; font-size: var(--fs-sm); color: var(--danger); }
</style>
