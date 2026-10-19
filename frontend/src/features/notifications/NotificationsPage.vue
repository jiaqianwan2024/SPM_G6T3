<template>
  <div class="notifications">
    <button type="button" class="btn btn-ghost back" @click="router.push('/app')">← Dashboard</button>
    <header class="page-head">
      <div>
        <p class="eyebrow">Inbox</p>
        <h1>Notifications</h1>
      </div>
      <div class="actions">
        <button
          type="button"
          class="btn btn-ghost"
          :class="{ active: unreadOnly }"
          :aria-pressed="unreadOnly"
          data-testid="notification-filter-unread"
          @click="toggleFilter"
        >
          Unread only
        </button>
        <button
          type="button"
          class="btn btn-ghost"
          :disabled="!unreadCount || markingAll"
          data-testid="notification-mark-all-read"
          @click="markAll"
        >
          {{ markingAll ? 'Marking…' : 'Mark all read' }}
        </button>
      </div>
    </header>

    <p v-if="loading" class="empty-note">Loading notifications…</p>
    <p v-else-if="error" class="form-error">{{ error }}</p>
    <p v-else-if="!items.length" class="empty-note" data-testid="notifications-empty">
      {{ unreadOnly ? 'You have no unread notifications.' : 'You have no notifications.' }}
    </p>

    <template v-else>
      <ul class="list">
        <li
          v-for="item in items"
          :key="item.notificationId"
          class="item"
          :class="{ unread: !item.isRead }"
          tabindex="0"
          data-testid="notification-row"
          :data-read="String(item.isRead)"
          @click="open(item)"
          @keydown.enter="open(item)"
        >
          <span v-if="!item.isRead" class="dot" aria-label="Unread"></span>
          <div class="item-body">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-text">{{ item.body }}</div>
            <div class="item-time">{{ formatSgt(item.createdAt) }}</div>
          </div>
          <button
            v-if="!item.isRead"
            type="button"
            class="btn btn-ghost mark-one"
            data-testid="notification-mark-read"
            @click.stop="markOne(item)"
          >
            Mark read
          </button>
        </li>
      </ul>
      <button
        v-if="hasMore"
        type="button"
        class="btn btn-ghost more"
        :disabled="loadingMore"
        data-testid="notification-load-more"
        @click="loadMore"
      >
        {{ loadingMore ? 'Loading…' : 'Load more' }}
      </button>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../api/notificationService.js'
import { formatSgt } from '../../utils/datetime.js'
import { refreshUnreadCount, unreadCount } from './unreadCount.js'

// SPM-94 AC8: the list is fetched a page at a time.
const PAGE_SIZE = 20

const router = useRouter()

const items = ref([])
const page = ref(1)
const hasMore = ref(false)
const unreadOnly = ref(false)
const loading = ref(true)
const loadingMore = ref(false)
const markingAll = ref(false)
const error = ref('')

async function fetchPage(pageNumber) {
  const { data } = await getNotifications({
    unreadOnly: unreadOnly.value || undefined,
    page: pageNumber,
    pageSize: PAGE_SIZE,
  })
  hasMore.value = data.length === PAGE_SIZE
  return data
}

async function load() {
  loading.value = true
  error.value = ''
  page.value = 1
  try {
    items.value = await fetchPage(1)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load notifications. Please try again.'
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  loadingMore.value = true
  try {
    const more = await fetchPage(page.value + 1)
    page.value += 1
    const seen = new Set(items.value.map((item) => item.notificationId))
    items.value = [...items.value, ...more.filter((item) => !seen.has(item.notificationId))]
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not load more notifications. Please try again.'
  } finally {
    loadingMore.value = false
  }
}

function toggleFilter() {
  unreadOnly.value = !unreadOnly.value
  load()
}

// AC3 and AC5: opening goes through the follow route, which marks it read and
// then takes the user to what it concerns, or says it is no longer available.
function open(item) {
  router.push({ name: 'notification-follow', params: { id: item.notificationId } })
}

// AC4: mark one read without leaving the list.
async function markOne(item) {
  try {
    await markNotificationRead(item.notificationId)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not mark that notification read. Please try again.'
    return
  }
  error.value = ''
  item.isRead = true
  if (unreadOnly.value) items.value = items.value.filter((row) => row.notificationId !== item.notificationId)
  refreshUnreadCount()
}

async function markAll() {
  markingAll.value = true
  try {
    await markAllNotificationsRead()
    error.value = ''
    unreadCount.value = 0
    if (unreadOnly.value) {
      items.value = []
      hasMore.value = false
    } else {
      items.value = items.value.map((item) => ({ ...item, isRead: true }))
    }
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not mark everything read. Please try again.'
  } finally {
    markingAll.value = false
  }
}

onMounted(() => {
  load()
  refreshUnreadCount()
})
</script>

<style scoped>
.notifications {
  max-width: 760px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}
.back { margin: 0 0 18px -18px; padding-left: 18px; }
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}
.page-head h1 { margin: 6px 0 0; font-size: 28px; font-weight: 500; letter-spacing: -.02em; }
.actions { display: flex; gap: 8px; }
.btn.active { border-color: rgba(167, 139, 250, .6); color: var(--text); }
.empty-note { font-size: 14px; color: var(--muted); }
.form-error {
  color: #ff8a76;
  font-size: 13px;
  background: rgba(255, 138, 118, .08);
  border: 1px solid rgba(255, 138, 118, .25);
  border-radius: 9px;
  padding: 11px 14px;
}

.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 14px 16px;
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: 14px;
  cursor: pointer;
  transition: border-color .2s var(--ease-out), background .2s var(--ease-out);
}
.item:hover, .item:focus-visible { border-color: rgba(167, 139, 250, .4); background: var(--glass-strong); outline: none; }
.item.unread .item-title { color: var(--text); font-weight: 600; }
.dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--iris-soft, #A78BFA);
  flex-shrink: 0;
}
.item:not(.unread) .item-body { padding-left: 18px; }
.item-body { flex: 1; min-width: 0; }
.item-title { font-size: 14px; color: var(--body); margin-bottom: 3px; }
.item-text { font-size: 13px; color: var(--muted); line-height: 1.5; }
.item-time { font-size: 11px; color: var(--muted); margin-top: 6px; }
.mark-one { flex-shrink: 0; font-size: 12px; }
.more { margin: 16px auto 0; display: block; }
</style>
