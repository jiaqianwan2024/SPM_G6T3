<template>
  <!-- SPM-57: Venue Staff's home screen. What is waiting on them and what is happening in the venues,
       grouped by venue so a long queue stays short. Every item opens the screen where that work is done. -->
  <div class="venue-dashboard" data-testid="venue-dashboard">
    <UiAlert v-if="error" tone="danger" data-testid="venue-dashboard-error">{{ error }}</UiAlert>

    <!-- The filters narrow all three sections and their counts at once. -->
    <div class="filters" data-testid="venue-filters">
      <UiField label="Venue" v-slot="f">
        <UiSelect v-model="filters.venueId" :options="venueOptions" v-bind="f" data-testid="venue-filter-venue" />
      </UiField>
      <UiField label="Event" v-slot="f">
        <UiInput v-model="filters.search" type="search" placeholder="Search by event name" v-bind="f" data-testid="venue-filter-search" />
      </UiField>
      <UiField label="Event date" v-slot="f">
        <UiSelect v-model="filters.within" :options="WITHIN" v-bind="f" data-testid="venue-filter-within" />
      </UiField>
      <UiButton v-if="filtering" variant="ghost" size="sm" class="clear" data-testid="venue-filter-clear" @click="clearFilters">
        Clear filters
      </UiButton>
    </div>

    <StatGrid>
      <StatCard
        v-for="section in SECTIONS"
        :key="section.key"
        :label="section.title"
        :value="loading || error ? '–' : shown[section.key].length"
        :hint="filtering && !loading && !error ? `Of ${board[section.key].length} in all` : text(section.hint)"
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
      :count="loading || error ? null : shown[section.key].length"
      :data-testid="`venue-section-${section.key}`"
    >
      <UiSkeleton v-if="loading" :lines="2" height="44px" />
      <UiEmptyState
        v-else-if="!board[section.key].length"
        :title="text(section.empty)"
        :hint="text(section.emptyHint)"
        :data-testid="`venue-${section.key}-empty`"
      />
      <UiEmptyState
        v-else-if="!shown[section.key].length"
        :title="`Nothing here matches the filters`"
        hint="Change or clear the filters to see the rest."
        :data-testid="`venue-${section.key}-no-match`"
      />
      <div v-else class="groups">
        <div
          v-for="group in groups[section.key]"
          :key="group.venueId"
          class="group"
          :class="{ open: isOpen(section.key, group), attention: section.key === 'reverification' }"
          :data-testid="`venue-${section.key}-group-${group.venueId}`"
        >
          <button
            type="button"
            class="group-head"
            :aria-expanded="isOpen(section.key, group)"
            :aria-controls="`venue-${section.key}-rows-${group.venueId}`"
            :data-testid="`venue-${section.key}-group-${group.venueId}-toggle`"
            @click="toggle(section.key, group)"
          >
            <span class="chevron" aria-hidden="true" />
            <span class="group-name">{{ group.venueName }}</span>
            <span class="count">{{ group.rows.length }}</span>
            <span class="group-summary">{{ summary(section.key, group) }}</span>
          </button>

          <ul v-if="isOpen(section.key, group)" :id="`venue-${section.key}-rows-${group.venueId}`" class="rows">
            <li v-for="row in visibleRows(section.key, group)" :key="row.bookingId">
              <button
                type="button"
                class="row"
                :data-testid="`venue-${section.key}-${row.bookingId}`"
                @click="open(section.key, row)"
              >
                <span class="row-title">
                  {{ eventName(row) }}
                  <span v-if="row.hold?.state === 'active'" class="tag">On hold</span>
                </span>
                <span class="row-when" :data-testid="`venue-${section.key}-${row.bookingId}-datetime`">{{ when(row) }}</span>
                <span class="row-meta">{{ detail(section.key, row) }}</span>
                <span class="row-action">{{ section.action }} <span aria-hidden="true">›</span></span>
                <span v-if="section.key === 'reverification' && row.reverificationNote" class="row-note">
                  {{ row.reverificationNote }}
                </span>
              </button>
            </li>
            <li v-if="group.rows.length > visibleRows(section.key, group).length">
              <button
                type="button"
                class="more"
                :data-testid="`venue-${section.key}-group-${group.venueId}-more`"
                @click="expanded[`${section.key}:${group.venueId}`] = true"
              >
                Show all {{ group.rows.length }}
              </button>
            </li>
          </ul>
        </div>
      </div>
    </SectionBlock>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getVenueDashboard } from '../../api/venueService.js'
import SectionBlock from '../../components/layout/SectionBlock.vue'
import StatCard from '../../components/layout/StatCard.vue'
import StatGrid from '../../components/layout/StatGrid.vue'
import UiAlert from '../../components/ui/UiAlert.vue'
import UiButton from '../../components/ui/UiButton.vue'
import UiEmptyState from '../../components/ui/UiEmptyState.vue'
import UiField from '../../components/ui/UiField.vue'
import UiInput from '../../components/ui/UiInput.vue'
import UiSelect from '../../components/ui/UiSelect.vue'
import UiSkeleton from '../../components/ui/UiSkeleton.vue'
import { formatSgt, formatSgtDate, formatSgtRange, formatSgtTime, parseServerTime } from '../../utils/datetime.js'

const SECTIONS = [
  {
    key: 'pending',
    title: 'Booking requests awaiting you',
    hint: 'Oldest first',
    action: 'Approve or reject',
    empty: 'No booking requests are waiting for a decision',
    emptyHint: 'New venue requests from coordinators show up here.',
  },
  {
    key: 'reverification',
    title: 'Needs re-verification',
    hint: 'After an event change',
    action: 'Re-confirm',
    empty: 'No bookings need re-verification',
    emptyHint: 'A confirmed booking shows up here when its event changes significantly.',
  },
  {
    key: 'upcoming',
    title: 'Coming up',
    hint: 'Next {days} days',
    action: 'Venue calendar',
    empty: 'No confirmed bookings in the next {days} days',
    emptyHint: 'Confirmed bookings appear here {days} days ahead, so each day can be prepared.',
  },
]

const WITHIN = [
  { value: '', label: 'Any time' },
  { value: '7', label: 'In the next 7 days' },
  { value: '30', label: 'In the next 30 days' },
  { value: '90', label: 'In the next 90 days' },
]

// A venue with a long queue shows this many rows until "Show all" is clicked.
const ROWS_SHOWN = 10
// A section with this many items or fewer starts with every venue open: short lists stay one click closer.
const OPEN_UP_TO = 5
const DAY_MS = 24 * 60 * 60 * 1000
const FILTERS_KEY = 'venue-home-filters'

const router = useRouter()
const board = reactive({ pending: [], reverification: [], upcoming: [], upcomingDays: 7 })
const loading = ref(true)
const error = ref('')
const filters = reactive({ venueId: '', search: '', within: '', ...savedFilters() })
const opened = reactive({})
const expanded = reactive({})

onMounted(async () => {
  try {
    const { data } = await getVenueDashboard()
    Object.assign(board, data)
    if (filters.venueId && !venueOptions.value.some((option) => option.value === filters.venueId)) filters.venueId = ''
  } catch {
    error.value = 'Could not load your venue work. Please try again.'
  } finally {
    loading.value = false
  }
})

// The filters stay as they were when Venue Staff come back from an item they opened.
watch(filters, () => {
  try {
    sessionStorage.setItem(FILTERS_KEY, JSON.stringify(filters))
  } catch {
    // Storage can be blocked; the filters then just start empty next time.
  }
})

function savedFilters() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(FILTERS_KEY) || '{}')
    return { venueId: String(saved.venueId || ''), search: String(saved.search || ''), within: String(saved.within || '') }
  } catch {
    return {}
  }
}

// Only venues that have something on the dashboard are worth choosing.
const venueOptions = computed(() => {
  const names = new Map()
  for (const section of SECTIONS) {
    for (const row of board[section.key]) names.set(row.venueId, venueName(row))
  }
  const venues = [...names].sort((a, b) => a[1].localeCompare(b[1])).map(([value, label]) => ({ value, label }))
  return [{ value: '', label: 'All venues' }, ...venues]
})

const filtering = computed(() => Boolean(filters.venueId || filters.search.trim() || filters.within))

function matches(row) {
  if (filters.venueId && row.venueId !== filters.venueId) return false
  const search = filters.search.trim().toLowerCase()
  if (search && !eventName(row).toLowerCase().includes(search)) return false
  if (filters.within) {
    const starts = parseServerTime(row.startsAt)
    if (!starts || starts.getTime() > Date.now() + Number(filters.within) * DAY_MS) return false
  }
  return true
}

const shown = computed(() => Object.fromEntries(SECTIONS.map(({ key }) => [key, board[key].filter(matches)])))

// Groups keep the server's order: a venue comes where its first item does (oldest request, soonest booking).
const groups = computed(() =>
  Object.fromEntries(
    SECTIONS.map(({ key }) => {
      const byVenue = new Map()
      for (const row of shown.value[key]) {
        if (!byVenue.has(row.venueId)) byVenue.set(row.venueId, { venueId: row.venueId, venueName: venueName(row), rows: [] })
        byVenue.get(row.venueId).rows.push(row)
      }
      return [key, [...byVenue.values()]]
    }),
  ),
)

// A venue's list starts closed, unless it is the only venue in the section or the section is short.
function isOpen(key, group) {
  return opened[`${key}:${group.venueId}`] ?? (groups.value[key].length === 1 || shown.value[key].length <= OPEN_UP_TO)
}

function toggle(key, group) {
  opened[`${key}:${group.venueId}`] = !isOpen(key, group)
}

function visibleRows(key, group) {
  return expanded[`${key}:${group.venueId}`] ? group.rows : group.rows.slice(0, ROWS_SHOWN)
}

function clearFilters() {
  Object.assign(filters, { venueId: '', search: '', within: '' })
}

// The look-ahead comes from the server (`upcomingDays`), so the words always match the list.
function text(words) {
  return words.replaceAll('{days}', String(board.upcomingDays))
}

function eventName(row) {
  return row.eventSnapshot?.eventName || `Event ${row.eventId}`
}

function venueName(row) {
  return row.venueName || `Venue ${row.venueId}`
}

function when(row) {
  return formatSgtRange(row.startsAt, row.endsAt) || 'Date not set'
}

function summary(key, group) {
  if (key === 'pending') return `Oldest sent ${formatSgtDate(group.rows[0].createdAt)}`
  return `Next on ${formatSgtDate(group.rows[0].startsAt)}`
}

function detail(key, row) {
  if (key === 'pending') return `Sent ${formatSgt(row.createdAt)}`
  if (key === 'reverification') return 'Event changed after approval'
  return `Setup from ${formatSgtTime(row.setupStartsAt)}`
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

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3) var(--space-4);
}
.filters > :deep(.field) { flex: 1 1 200px; min-width: 0; }
.filters > :deep(.field:nth-child(2)) { flex-grow: 1.4; }
.clear { margin-bottom: 4px; }

.groups { display: grid; gap: var(--space-2); }
.group {
  background: var(--glass);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  overflow: hidden;
}
.group.attention { border-color: rgba(245, 196, 81, .45); }
.group-head {
  width: 100%;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-3) var(--space-5);
  text-align: left;
  font: inherit;
  color: var(--body);
  background: none;
  border: 0;
  cursor: pointer;
  transition: background .3s var(--ease-out);
}
.group-head:hover { background: var(--glass-strong); }
.group-head:focus-visible { outline: 2px solid var(--iris-soft); outline-offset: -2px; }
.chevron {
  width: 8px;
  height: 8px;
  border-right: 1.6px solid var(--icon);
  border-bottom: 1.6px solid var(--icon);
  transform: rotate(-45deg);
  transition: transform .25s var(--ease-out);
}
.group.open .chevron { transform: rotate(45deg); }
.group-name { color: var(--text); font-size: var(--fs-md); font-weight: 500; }
.count {
  padding: 1px 9px;
  border-radius: var(--radius-pill);
  background: var(--glass-strong);
  font-size: var(--fs-xs);
}
.group-summary { margin-left: auto; font-size: var(--fs-xs); color: var(--muted); }

.rows { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--hairline); }
.rows li + li { border-top: 1px solid var(--hairline); }
.row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1.4fr) minmax(0, 1.1fr) auto;
  align-items: center;
  gap: var(--space-1) var(--space-4);
  padding: var(--space-3) var(--space-5);
  text-align: left;
  font: inherit;
  font-size: var(--fs-sm);
  color: var(--body);
  background: none;
  border: 0;
  cursor: pointer;
  transition: background .3s var(--ease-out);
}
.row:hover { background: var(--glass-strong); }
.row:focus-visible { outline: 2px solid var(--iris-soft); outline-offset: -2px; }
.row-title { color: var(--text); font-weight: 500; display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
.row-meta { font-size: var(--fs-xs); color: var(--muted); }
.row-action { font-size: var(--fs-xs); color: var(--iris-soft); white-space: nowrap; }
.row-note { grid-column: 1 / -1; font-size: var(--fs-xs); color: var(--text); }
.tag {
  font-size: var(--fs-xs);
  font-weight: 400;
  color: var(--muted);
  border: 1px solid var(--hairline);
  border-radius: var(--radius-pill);
  padding: 1px var(--space-2);
}
.more {
  width: 100%;
  padding: var(--space-3) var(--space-5);
  font: inherit;
  font-size: var(--fs-xs);
  color: var(--iris-soft);
  text-align: left;
  background: none;
  border: 0;
  cursor: pointer;
}
.more:hover { background: var(--glass-strong); }
.more:focus-visible { outline: 2px solid var(--iris-soft); outline-offset: -2px; }

@media (max-width: 720px) {
  .filters > :deep(.field) { flex-basis: 100%; }
  .row { grid-template-columns: 1fr; }
  .group-summary { margin-left: 0; width: 100%; }
}
</style>
