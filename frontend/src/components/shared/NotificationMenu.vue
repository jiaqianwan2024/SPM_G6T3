<template>
  <div class="notification-menu" role="dialog" aria-label="Notifications" data-testid="notification-panel">
    <div class="head">
      <div class="head-actions">
        <button type="button" class="head-btn" data-testid="notification-see-all" @click="$emit('see-all')">See all</button>
        <button
          type="button"
          class="head-btn"
          :disabled="markingAll || !hasUnread"
          data-testid="notification-mark-all-read"
          @click="$emit('mark-all')"
        >
          {{ markingAll ? 'Marking…' : 'Mark all read' }}
        </button>
        <button
          type="button"
          class="head-btn"
          :disabled="clearing || !items.length"
          data-testid="notification-clear-all"
          @click="$emit('clear-all')"
        >
          {{ clearing ? 'Clearing…' : 'Clear all' }}
        </button>
      </div>
    </div>

    <p v-if="loading" class="note">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else-if="!items.length" class="note" data-testid="notification-empty">You're all caught up.</p>

    <ul v-else class="list">
      <li v-for="item in items" :key="item.notificationId" class="item">
        <button
          type="button"
          class="row"
          :class="{ unread: !item.isRead }"
          :data-testid="`notification-${item.notificationId}`"
          @click="$emit('open', item)"
        >
          <span v-if="!item.isRead" class="dot"><span class="sr-only">Unread</span></span>
          <span class="detail">
            <span class="top">
              <span class="title">{{ item.title }}</span>
              <span class="time">{{ formatSgt12h(item.createdAt) }}</span>
            </span>
            <span class="text">{{ item.body }}</span>
          </span>
        </button>
        <button
          type="button"
          class="remove"
          :aria-label="`Delete notification: ${item.title}`"
          :data-testid="`notification-remove-${item.notificationId}`"
          @click="$emit('dismiss', item)"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4.5 7h15M9.5 7V5.2c0-.7.5-1.2 1.2-1.2h2.6c.7 0 1.2.5 1.2 1.2V7M6.5 7l.8 11.3c.1.9.8 1.7 1.7 1.7h6c.9 0 1.6-.8 1.7-1.7L17.5 7M10 11v5M14 11v5" />
          </svg>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatSgt12h } from '../../utils/datetime.js'

// The panel behind the navbar's bell, built like ProfileMenu: rows of title + description + time under a slim
// action row (See all, Mark all read).
// It only displays what it is given, so the /dev/ui catalogue can show it with sample data.
const props = defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  markingAll: { type: Boolean, default: false },
  clearing: { type: Boolean, default: false },
})
// Mark all read is only useful while something in the panel is unread.
const hasUnread = computed(() => props.items.some((item) => !item.isRead))

defineEmits(['open', 'see-all', 'mark-all', 'clear-all', 'dismiss'])
</script>

<style scoped>
.notification-menu {
  width: 400px;
  max-width: calc(100vw - 32px);
  max-height: 480px;
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  background: var(--profile-bg);
  border: 1px solid rgba(167, 139, 250, .28);
  border-radius: var(--radius);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
}

.head {
  flex-shrink: 0; /* stays put while the list below scrolls */
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-2) 0;
}
.head-actions { display: flex; align-items: center; gap: var(--space-1); }
.head-btn {
  padding: 2px var(--space-2);
  background: none;
  border: none;
  border-radius: var(--radius);
  font: var(--fs-xs) var(--font);
  color: var(--halo);
  cursor: pointer;
  transition: background .25s var(--ease-out);
}
.head-btn:hover:not(:disabled) { background: rgba(255, 255, 255, .08); }
.head-btn:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.head-btn:disabled { color: var(--muted); cursor: default; }

.note { margin: 0; padding: var(--space-3); font-size: var(--fs-sm); color: var(--muted); }
.error { margin: 0; padding: var(--space-3); font-size: var(--fs-sm); color: var(--danger); }

.list { list-style: none; margin: 0; padding: 0; overflow-y: auto; min-height: 0; overscroll-behavior: contain; }
.item { position: relative; }

.row {
  width: 100%;
  display: flex;
  align-items: flex-start;
  position: relative;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-3) var(--space-3) var(--space-4);
  background: none;
  border: none;
  border-radius: var(--radius);
  text-align: left;
  font: inherit;
  cursor: pointer;
  transition: background .25s var(--ease-out);
}
/* Same hover as the header icons and the Log Out row. */
.row:hover, .item:focus-within .row { background: rgba(255, 255, 255, .08); }
.row:focus-visible { outline: none; box-shadow: var(--focus-ring); }

/* The unread dot sits in the row's left padding, so the text gets the full width of the row. */
.dot {
  position: absolute;
  top: 17px;
  left: 4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #FF8A76;
}

.detail { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.title { font-size: var(--fs-sm); line-height: 20px; font-weight: 600; color: #FFFFFF; overflow-wrap: anywhere; }
.text {
  font-size: var(--fs-xs);
  line-height: 1.5;
  color: var(--muted);
  overflow-wrap: anywhere;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.title { min-width: 0; }
.time { flex-shrink: 0; font-size: var(--fs-xs); line-height: 20px; color: var(--muted); white-space: nowrap; }

.remove {
  position: absolute;
  /* centred on the title line and on the time's right edge, so it takes the time's place */
  top: 8px;
  right: calc(var(--space-3) - 5px);
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  padding: 0;
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--icon);
  cursor: pointer;
  opacity: 0;
  /* No fade on opacity: after a delete the next row slides under the pointer, and a fade there reads as flicker. */
  transition: background .2s var(--ease-out);
}
.remove svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.remove:hover { background: rgba(255, 255, 255, .12); }
.remove:focus-visible { outline: none; opacity: 1; box-shadow: var(--focus-ring); }
/* Like a mail list: on hover (or keyboard focus) the time gives way to the bin, in the same spot. */
.item:hover .remove, .item:focus-within .remove { opacity: 1; }
.item:hover .time, .item:focus-within .time { opacity: 0; }
/* Touch screens have no hover: show the bin always, beside the time, with room for it. */
@media (hover: none) {
  .remove { opacity: 1; }
  .item:hover .time, .item:focus-within .time { opacity: 1; }
  .top { padding-right: 32px; }
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
