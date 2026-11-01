<template>
  <div class="follow">
    <button type="button" class="btn btn-ghost back" @click="router.push('/app/notifications')">← Notifications</button>
    <p v-if="loading" class="empty-note">Opening notification…</p>
    <section v-else class="panel" data-testid="notification-unavailable">
      <h1>{{ headline }}</h1>
      <p>{{ detail }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { markNotificationRead } from '../../api/notificationService.js'
import { refreshUnreadCount } from './unreadCount.js'
import { notificationTarget } from './target.js'
import { session } from '../../store/session.js'

// SPM-94 AC3 and AC5: opening a notification marks it read and goes to the
// event or resource it concerns. A notification that is gone, or that is not
// the signed-in user's, gets a plain message here instead of an error page.
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const state = ref('unavailable')

const headline = computed(() =>
  state.value === 'no-target' ? 'Nothing more to open' : 'This notification is no longer available'
)
const detail = computed(() =>
  state.value === 'no-target'
    ? 'This notification does not link to anything. It has been marked read.'
    : 'It may have been removed, or it may not be yours to see.'
)

onMounted(async () => {
  try {
    const { data } = await markNotificationRead(route.params.id)
    refreshUnreadCount()
    const target = notificationTarget(data, session.role)
    if (target) {
      router.replace(target)
      return
    }
    state.value = 'no-target'
  } catch {
    state.value = 'unavailable'
  }
  loading.value = false
})
</script>

<style scoped>
.follow { max-width: 760px; margin: 0 auto; padding: 28px 32px 48px; }
.back { margin: 0 0 18px -18px; padding-left: 18px; }
.empty-note { font-size: 14px; color: var(--muted); }
.panel {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  padding: 28px 24px;
}
.panel h1 { margin: 0 0 8px; font-size: 20px; font-weight: 500; color: var(--text); }
.panel p { margin: 0; font-size: 14px; color: var(--body); }
</style>
