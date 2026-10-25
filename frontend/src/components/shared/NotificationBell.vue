<template>
  <div class="bell-wrap" :class="{ inline }">
    <button
      type="button"
      class="bell-btn"
      data-testid="notification-bell"
      :aria-label="unreadCount ? `Notifications, ${unreadCount} unread` : 'Notifications'"
      @click="toggle"
    >
      <svg viewBox="0 0 24 24" class="bell-icon" aria-hidden="true">
        <path
          d="M12 3.5c-2.9 0-5.1 2.2-5.1 5.2v3.1c0 .6-.2 1.2-.6 1.7l-1.1 1.4c-.6.8 0 2 1 2h11.6c1 0 1.6-1.2 1-2l-1.1-1.4c-.4-.5-.6-1.1-.6-1.7V8.7c0-3-2.2-5.2-5.1-5.2z"
          fill="none"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linejoin="round"
        />
        <path d="M10.2 19.5a1.9 1.9 0 0 0 3.6 0" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
      </svg>
      <span v-if="unreadCount > 0" class="badge" data-testid="notification-unread-count">
        {{ unreadCount > 9 ? '9+' : unreadCount }}
      </span>
    </button>

    <div v-if="open" class="backdrop" @click="close"></div>

    <NotificationMenu
      v-if="open"
      class="panel"
      :items="items"
      :loading="loading"
      :error="error"
      :marking-all="markingAll"
      :clearing="clearing"
      @open="openItem"
      @see-all="seeAll"
      @mark-all="markAll"
      @clear-all="clearAll"
      @dismiss="dismiss"
    />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  clearAllNotifications,
  clearNotification,
  getNotifications,
  markAllNotificationsRead,
} from '../../api/notificationService.js'
import NotificationMenu from './NotificationMenu.vue'
import { refreshUnreadCount, unreadCount } from '../../features/notifications/unreadCount.js'

// `inline` places the bell in the flow (the app shell's top bar) instead of pinning it to the viewport corner.
defineProps({ inline: { type: Boolean, default: false } })

const router = useRouter()

const open = ref(false)
const items = ref([])
const loading = ref(false)
const error = ref('')
const markingAll = ref(false)
const clearing = ref(false)

let pollTimer = null

async function loadList() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getNotifications({ pageSize: 20, bell: true })
    items.value = data
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load notifications. Please try again.'
  } finally {
    loading.value = false
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) loadList()
}

function close() {
  open.value = false
}

// AC3/AC5: the follow route marks the notification read and goes to what it
// concerns, or says plainly that it is no longer available.
function openItem(item) {
  close()
  router.push({ name: 'notification-follow', params: { id: item.notificationId } })
}

function seeAll() {
  close()
  router.push({ name: 'notifications' })
}

async function markAll() {
  markingAll.value = true
  try {
    await markAllNotificationsRead()
    items.value = items.value.map((item) => ({ ...item, isRead: true }))
    unreadCount.value = 0
  } catch {
    // Best effort - leaves the list as it was; the user can try again.
  } finally {
    markingAll.value = false
  }
}

// Removes one row straight away (optimistic); if the server call fails the row comes back.
async function dismiss(item) {
  const index = items.value.findIndex((n) => n.notificationId === item.notificationId)
  if (index === -1) return
  items.value = items.value.filter((n) => n.notificationId !== item.notificationId)
  if (!item.isRead && unreadCount.value > 0) unreadCount.value -= 1
  try {
    await clearNotification(item.notificationId)
  } catch {
    items.value.splice(Math.min(index, items.value.length), 0, item)
    if (!item.isRead) unreadCount.value += 1
  }
}

async function clearAll() {
  clearing.value = true
  try {
    await clearAllNotifications()
    items.value = []
    unreadCount.value = 0
  } catch {
    // Best effort - leaves the list as it was; the user can try again.
  } finally {
    clearing.value = false
  }
}

onMounted(() => {
  refreshUnreadCount()
  pollTimer = setInterval(refreshUnreadCount, 30000)
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.bell-wrap {
  position: fixed;
  top: 20px;
  right: 28px;
  z-index: 50;
}

.bell-wrap.inline { position: relative; top: auto; right: auto; }
/* In the app's top bar the bell matches the other header icons: bare, 24px, soft hover. */
.bell-wrap.inline .bell-btn {
  background: none;
  border: none;
  border-radius: var(--radius);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}
.bell-wrap.inline .bell-btn:hover { background: rgba(255, 255, 255, .08); }
.bell-wrap.inline .bell-btn:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.bell-wrap.inline .bell-icon { width: 24px; height: 24px; }
.bell-wrap.inline .badge { top: 2px; right: 2px; }

.bell-btn {
  position: relative;
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: 50%;
  color: var(--icon);
  cursor: pointer;
  transition: border-color .3s var(--ease-out), background .3s var(--ease-out);
}
.bell-btn:hover { border-color: rgba(167, 139, 250, .4); background: var(--glass-strong); }
.bell-icon { width: 19px; height: 19px; }

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  border-radius: 999px;
  background: #FF8A76;
  color: #1A0C3B;
  font-size: 10px;
  font-weight: 600;
  line-height: 17px;
  text-align: center;
}

.backdrop { position: fixed; inset: 0; z-index: 49; }

/* The panel's look lives in NotificationMenu; the bell only places it. */
.panel { position: absolute; top: 50px; right: 0; z-index: 50; }

@media (max-width: 480px) {
  .bell-wrap:not(.inline) { top: 12px; right: 14px; }
  .bell-wrap:not(.inline) .panel { right: -8px; }
}
</style>
