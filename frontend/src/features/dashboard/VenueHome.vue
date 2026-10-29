<template>
  <!-- SPM-57: Venue Staff's home screen. What is waiting on them and what is happening in the venues.
       Every item opens the screen where that work is done. -->
  <div class="venue-dashboard" data-testid="venue-dashboard">
    <UiAlert v-if="error" tone="danger" data-testid="venue-dashboard-error">{{ error }}</UiAlert>

    <StatGrid>
      <StatCard
        v-for="section in SECTIONS"
        :key="section.key"
        :label="section.title"
        :value="loading || error ? '–' : board[section.key].length"
        :hint="text(section.hint)"
        to="section"
        :data-testid="`venue-count-${section.key}`"
        @open="jumpTo(section.key)"
      />
    </StatGrid>

    <SectionBlock
      v-for="section in SECTIONS"
      :id="`venue-section-${section.key}`"
      :key="section.key"
      :title="section.title"
      :count="loading || error ? null : board[section.key].length"
      :data-testid="`venue-section-${section.key}`"
    >
      <UiSkeleton v-if="loading" :lines="2" height="44px" />
      <UiEmptyState
        v-else-if="!board[section.key].length"
        :title="text(section.empty)"
        :hint="text(section.emptyHint)"
        :data-testid="`venue-${section.key}-empty`"
      />
      <ul v-else class="items">
        <li v-for="row in board[section.key]" :key="row.bookingId">
          <button
            type="button"
            class="item"
            :class="{ attention: section.key === 'reverification' }"
            :data-testid="`venue-${section.key}-${row.bookingId}`"
            @click="open(section.key, row)"
          >
            <span class="item-head">
              <span class="item-title">{{ eventName(row) }}</span>
              <span v-if="row.hold?.state === 'active'" class="tag">On hold</span>
            </span>
            <span class="item-body">
              {{ row.venueName || 'Venue' }} ·
              <span :data-testid="`venue-${section.key}-${row.bookingId}-datetime`">{{ when(row) }}</span>
            </span>
            <span v-if="section.key === 'reverification' && row.reverificationNote" class="item-note">
              {{ row.reverificationNote }}
            </span>
            <span class="item-meta">{{ detail(section.key, row) }}</span>
          </button>
        </li>
      </ul>
    </SectionBlock>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getVenueDashboard } from '../../api/venueService.js'
import SectionBlock from '../../components/layout/SectionBlock.vue'
import StatCard from '../../components/layout/StatCard.vue'
import StatGrid from '../../components/layout/StatGrid.vue'
import UiAlert from '../../components/ui/UiAlert.vue'
import UiEmptyState from '../../components/ui/UiEmptyState.vue'
import UiSkeleton from '../../components/ui/UiSkeleton.vue'
import { formatSgt, formatSgtRange, formatSgtTime } from '../../utils/datetime.js'

const SECTIONS = [
  {
    key: 'pending',
    title: 'Booking requests awaiting you',
    hint: 'Oldest first',
    empty: 'No booking requests are waiting for a decision',
    emptyHint: 'New venue requests from coordinators show up here.',
  },
  {
    key: 'reverification',
    title: 'Needs re-verification',
    hint: 'After an event change',
    empty: 'No bookings need re-verification',
    emptyHint: 'A confirmed booking shows up here when its event changes significantly.',
  },
  {
    key: 'upcoming',
    title: 'Coming up',
    hint: 'Next {days} days',
    empty: 'No confirmed bookings in the next {days} days',
    emptyHint: 'Confirmed bookings appear here {days} days ahead, so each day can be prepared.',
  },
]

const router = useRouter()
const board = reactive({ pending: [], reverification: [], upcoming: [], upcomingDays: 7 })
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await getVenueDashboard()
    Object.assign(board, data)
  } catch {
    error.value = 'Could not load your venue work. Please try again.'
  } finally {
    loading.value = false
  }
})

// The look-ahead comes from the server (`upcomingDays`), so the words always match the list.
function text(words) {
  return words.replaceAll('{days}', String(board.upcomingDays))
}

function eventName(row) {
  return row.eventSnapshot?.eventName || `Event ${row.eventId}`
}

function when(row) {
  return formatSgtRange(row.startsAt, row.endsAt) || 'Date not set'
}

function detail(key, row) {
  if (key === 'pending') return `Submitted ${formatSgt(row.createdAt)} · Open to approve or reject`
  if (key === 'reverification') return 'Open to re-confirm the booking'
  return `Setup from ${formatSgtTime(row.setupStartsAt)} · Open on the venue calendar`
}

// AC4: each list opens the screen where that work is done.
function open(key, row) {
  if (key === 'upcoming') {
    router.push({ name: 'dashboard', query: { tab: 'Venue Calendar', venue: row.venueId, at: row.startsAt } })
    return
  }
  const status = key === 'pending' ? 'pending' : 'approved'
  router.push({ name: 'dashboard', query: { tab: 'Booking Requests', status, booking: row.bookingId } })
}

function jumpTo(key) {
  document.getElementById(`venue-section-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<style scoped>
.venue-dashboard { display: flex; flex-direction: column; gap: var(--space-5); }

.items { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.item {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-5);
  text-align: left;
  font: inherit;
  color: var(--body);
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color .3s var(--ease-out), background .3s var(--ease-out);
}
.item:hover { border-color: rgba(167, 139, 250, .4); background: var(--glass-strong); }
.item:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.item.attention { border-color: rgba(245, 196, 81, .45); }
.item-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2) var(--space-3); }
.item-title { color: var(--text); font-size: var(--fs-md); font-weight: 500; }
.item-body { font-size: var(--fs-sm); }
.item-note { font-size: var(--fs-sm); color: var(--text); }
.item-meta { font-size: var(--fs-xs); color: var(--muted); }
.tag {
  font-size: var(--fs-xs);
  color: var(--muted);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-pill);
  padding: 1px var(--space-2);
}
</style>
