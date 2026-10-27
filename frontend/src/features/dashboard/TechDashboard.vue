<template>
  <!-- SPM-58: Technical Support's home screen. What is waiting on the team, and the events it supplies.
       Every item opens the event's equipment page, where the work is done. -->
  <div class="tech-dashboard" data-testid="tech-dashboard">
    <div class="counts">
      <button
        v-for="section in SECTIONS"
        :key="section.key"
        type="button"
        class="count"
        :data-testid="`tech-count-${section.id}`"
        @click="jumpTo(section.id)"
      >
        <span class="count-value">{{ loaded ? board[section.key].length : '–' }}</span>
        <span class="count-label">{{ section.title }}</span>
      </button>
    </div>

    <p v-if="loadError" class="form-error" data-testid="tech-dashboard-error">{{ loadError }}</p>

    <section
      v-for="section in SECTIONS"
      :id="`tech-section-${section.id}`"
      :key="section.key"
      class="block"
      :data-testid="`tech-section-${section.id}`"
    >
      <h3>{{ section.title }}</h3>
      <p v-if="!loaded" class="empty-note">Loading…</p>
      <p v-else-if="!board[section.key].length" class="empty-note" :data-testid="`tech-${section.id}-empty`">
        {{ section.empty }}
      </p>

      <template v-else-if="section.key === 'upcoming'">
        <router-link
          v-for="row in board.upcoming"
          :key="row.eventId"
          class="item"
          :to="workScreen(row.eventId)"
          data-testid="tech-upcoming"
        >
          <span class="item-name">{{ row.eventName }}</span>
          <span class="item-meta">{{ when(row) }} · {{ row.equipmentSummary }}</span>
        </router-link>
      </template>

      <template v-else>
        <router-link
          v-for="row in board[section.key]"
          :key="row.id"
          class="item"
          :to="workScreen(row.eventId)"
          :data-testid="`tech-${section.id}-${row.id}`"
        >
          <span class="item-head">
            <span class="item-name">{{ row.eventName }}</span>
            <span v-if="section.key === 'shortfalls'" class="flag">{{ shortfallLabel(row) }}</span>
            <span v-else-if="section.key === 'reverification'" class="flag">Needs re-verification</span>
          </span>
          <span class="item-meta">
            <span :data-testid="`tech-${section.id}-${row.id}-date`">{{ when(row) }}</span>
            · {{ row.quantity }} × {{ row.equipmentName }}<template v-if="row.note"> · <span class="item-note">{{ row.note }}</span></template>
          </span>
        </router-link>
      </template>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getTechDashboard } from '../../api/equipmentService.js'
import { formatSgtRange } from '../../utils/datetime.js'

const SECTIONS = [
  {
    key: 'pending',
    id: 'pending',
    title: 'Requests awaiting review',
    empty: 'No equipment requests are waiting for review.'
  },
  {
    key: 'reverification',
    id: 'reverification',
    title: 'Needs re-verification',
    empty: 'No reservations need re-checking after an event change.'
  },
  {
    key: 'shortfalls',
    id: 'shortfall',
    title: 'Unresolved shortfalls',
    empty: 'No unavailable or partly fulfilled lines are waiting to be resolved.'
  },
  {
    key: 'upcoming',
    id: 'upcoming',
    title: 'Upcoming events we supply',
    empty: 'No upcoming events have equipment reserved.'
  }
]

const board = reactive({ pending: [], reverification: [], shortfalls: [], upcoming: [] })
const loaded = ref(false)
const loadError = ref('')

onMounted(async () => {
  try {
    const { data } = await getTechDashboard()
    Object.assign(board, data)
  } catch {
    loadError.value = 'Could not load your equipment work. Please try again.'
  } finally {
    loaded.value = true
  }
})

function jumpTo(id) {
  document.getElementById(`tech-section-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function workScreen(eventId) {
  return `/app/events/${eventId}/equipment`
}

function when(row) {
  return formatSgtRange(row.eventStartsAt, row.eventEndsAt) || 'Date not set'
}

function shortfallLabel(row) {
  if (row.status === 'unavailable') return `Unavailable · ${row.shortfall} short`
  return `Partly fulfilled · ${row.shortfall} of ${row.quantity} short`
}
</script>

<style scoped>
.tech-dashboard { display: flex; flex-direction: column; gap: 18px; }

.counts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.count {
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: var(--radius);
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  font: inherit;
  cursor: pointer;
  transition: border-color .15s ease;
}
.count:hover, .count:focus-visible { border-color: rgba(167, 139, 250, .38); outline: none; }
.block { scroll-margin-top: 16px; }
.count-value { font-family: var(--font); font-size: 26px; color: var(--text); }
.count-label { font-size: 12px; color: var(--muted); letter-spacing: .04em; }

.block h3 { margin: 0 0 10px; font-size: 15px; font-weight: 500; color: var(--text); }
.empty-note { font-size: 14px; color: var(--muted); margin: 0; line-height: 1.6; }

.item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: var(--glass);
  border: 1px solid var(--hairline);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius: var(--radius);
  padding: 10px 16px;
  margin-bottom: 8px;
  text-decoration: none;
  transition: border-color .15s ease;
}
.item:hover, .item:focus-visible { border-color: rgba(167, 139, 250, .38); outline: none; }
.item-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.item-name { font-family: var(--font); font-weight: 500; color: var(--text); font-size: 15px; }
.item-meta { font-size: 12px; color: var(--muted); line-height: 1.5; }
.item-note { color: var(--body); }
.flag {
  font-size: 10px;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #FFD9A8;
  background: rgba(255, 170, 80, .1);
  border: 1px solid rgba(255, 196, 120, .35);
  border-radius: 999px;
  padding: 2px 9px;
}

@media (max-width: 700px) {
  .counts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
