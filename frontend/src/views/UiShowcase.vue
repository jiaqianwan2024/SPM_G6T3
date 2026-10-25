<template>
  <div class="page">
    <PageHeader title="UI components" subtitle="Dev-only catalogue. Every shared primitive in its main states.">
      <template #actions><UiButton variant="outline" size="sm">Action</UiButton></template>
    </PageHeader>

    <SectionBlock title="Navbar">
      <p class="note">
        The app's top bar (<code>AppNavbar</code>): logo left, the role's tabs in the middle, notifications and
        profile right. Click the tabs to see the active underline. Icons are static here.
      </p>
      <div class="navbar-demo">
        <AppNavbar :tabs="navTabs" :active-tab="navTab" demo @select="navTab = $event" />
      </div>
      <p class="note">With many tabs (Technical Support has 8) the row scrolls sideways instead of wrapping.</p>
      <div class="navbar-demo">
        <AppNavbar :tabs="manyTabs" :active-tab="manyTab" demo @select="manyTab = $event" />
      </div>
    </SectionBlock>

    <SectionBlock title="Typography">
      <p class="note">
        One font family across the whole app: <strong>Inter</strong>, set once as <code>--font</code> in
        <code>main.css</code> and loaded in <code>index.html</code> (weights 300, 400, 500, 600).
        Use the size tokens below instead of raw pixel values.
      </p>
      <UiCard>
        <div class="type-list">
          <div v-for="w in weights" :key="w.value" class="type-row">
            <code>{{ w.value }}</code>
            <span class="sample" :style="{ fontWeight: w.value }">{{ w.label }} — The quick brown fox jumps over the lazy dog</span>
          </div>
        </div>
      </UiCard>
      <UiCard class="type-card">
        <div class="type-list">
          <div v-for="t in sizes" :key="t.token" class="type-row">
            <code>{{ t.token }} · {{ t.px }}</code>
            <span class="sample" :style="{ fontSize: `var(${t.token})` }">{{ t.use }}</span>
          </div>
          <div class="type-row">
            <code>.eyebrow</code>
            <span class="eyebrow">Section label</span>
          </div>
          <div class="type-row">
            <code>h2 / h3</code>
            <span><h2 class="demo-h">Page heading</h2><h3 class="demo-h">Section heading</h3></span>
          </div>
        </div>
      </UiCard>
    </SectionBlock>

    <SectionBlock title="Corner radius">
      <p class="note">
        One radius, <code>--radius</code> (12px), for every container: cards, fields, menus, dialogs, tables and
        hover highlights. Chips and pill buttons use <code>--radius-pill</code>; <code>--radius-sm</code> (8px) is
        only for small square buttons.
      </p>
      <div class="row">
        <div class="shape" style="border-radius: var(--radius)">Card / field / menu</div>
        <div class="shape hover-demo" style="border-radius: var(--radius)">Hover highlight</div>
        <span class="shape chip" style="border-radius: var(--radius-pill)">Chip</span>
        <span class="shape chip" style="border-radius: var(--radius-sm)">Small square button</span>
      </div>
    </SectionBlock>

    <SectionBlock title="Buttons">
      <div class="row">
        <UiButton>Solid</UiButton>
        <UiButton variant="outline">Outline</UiButton>
        <UiButton variant="ghost">Ghost</UiButton>
        <UiButton variant="danger">Danger</UiButton>
        <UiButton size="sm">Small</UiButton>
        <UiButton loading>Loading</UiButton>
        <UiButton disabled>Disabled</UiButton>
      </div>
    </SectionBlock>

    <SectionBlock title="Status pills">
      <div class="row">
        <StatusPill v-for="s in statuses" :key="s" :status="s" />
      </div>
    </SectionBlock>

    <SectionBlock title="Stat cards">
      <StatGrid>
        <StatCard label="Open clarifications" :value="3" hint="Needs your reply" to="x" @open="clicked = 'clarifications'" />
        <StatCard label="Confirmed" :value="12" />
        <StatCard label="Pending changes" value="–" />
      </StatGrid>
      <p v-if="clicked" class="note">Opened: {{ clicked }}</p>
    </SectionBlock>

    <SectionBlock title="Alerts">
      <div class="stack">
        <UiAlert>Your request is with the coordinator.</UiAlert>
        <UiAlert tone="success">Request submitted.</UiAlert>
        <UiAlert tone="warning">Venue changed, so this event needs reconfirming.</UiAlert>
        <UiAlert v-if="showAlert" tone="danger" dismissible @dismiss="showAlert = false">Could not save. Try again.</UiAlert>
      </div>
    </SectionBlock>

    <SectionBlock title="Tabs">
      <UiTabs v-model="tab" :tabs="[{ value: 'open', label: 'Open', count: 3 }, { value: 'done', label: 'Done', count: 12 }, 'Drafts']" />
      <p class="note">Selected: {{ tab }}</p>
    </SectionBlock>

    <SectionBlock title="Loading skeleton">
      <UiCard><UiSkeleton :lines="3" /></UiCard>
    </SectionBlock>

    <SectionBlock title="Form fields">
      <UiCard>
        <div class="form">
          <UiField label="Title" hint="Shown to attendees" required v-slot="f">
            <UiInput v-model="title" v-bind="f" />
          </UiField>
          <UiField label="Venue type" v-slot="f">
            <UiSelect v-model="kind" :options="['Hall', 'Studio', 'Outdoor']" placeholder="Choose one" v-bind="f" />
          </UiField>
          <UiField label="Description" error="Description is required" v-slot="f">
            <UiTextarea v-model="desc" v-bind="f" />
          </UiField>
        </div>
      </UiCard>
    </SectionBlock>

    <SectionBlock title="Table" :count="rows.length">
      <UiTable :columns="cols" :rows="rows">
        <template #cell-status="{ value }"><StatusPill :status="value" /></template>
      </UiTable>
    </SectionBlock>

    <SectionBlock title="Empty state">
      <UiTable :columns="cols" :rows="[]" empty-title="No events yet" empty-hint="Create a request to get started." />
    </SectionBlock>

    <SectionBlock title="Modal">
      <UiButton variant="outline" @click="open = true">Open modal</UiButton>
      <UiModal :open="open" title="Reject this request?" @close="open = false">
        <p class="note">Focus is trapped here. Esc or the overlay closes it.</p>
        <template #footer>
          <UiButton variant="ghost" @click="open = false">Cancel</UiButton>
          <UiButton variant="danger" @click="open = false">Reject</UiButton>
        </template>
      </UiModal>
    </SectionBlock>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppNavbar from '../components/layout/AppNavbar.vue'
import PageHeader from '../components/layout/PageHeader.vue'
import SectionBlock from '../components/layout/SectionBlock.vue'
import StatGrid from '../components/layout/StatGrid.vue'
import StatCard from '../components/layout/StatCard.vue'
import UiAlert from '../components/ui/UiAlert.vue'
import UiTabs from '../components/ui/UiTabs.vue'
import UiSkeleton from '../components/ui/UiSkeleton.vue'
import UiButton from '../components/ui/UiButton.vue'
import UiCard from '../components/ui/UiCard.vue'
import UiField from '../components/ui/UiField.vue'
import UiInput from '../components/ui/UiInput.vue'
import UiSelect from '../components/ui/UiSelect.vue'
import UiTextarea from '../components/ui/UiTextarea.vue'
import UiTable from '../components/ui/UiTable.vue'
import UiModal from '../components/ui/UiModal.vue'
import StatusPill from '../components/ui/StatusPill.vue'

const statuses = ['confirmed', 'under review', 'changes requested', 'safety review', 'safety approved', 'rejected', 'draft']
const cols = [{ key: 'name', label: 'Event' }, { key: 'status', label: 'Status' }, { key: 'date', label: 'Date' }]
const rows = [
  { id: 1, name: 'Orientation night', status: 'confirmed', date: '12 Nov' },
  { id: 2, name: 'Hackathon', status: 'under review', date: '20 Nov' },
]

const weights = [
  { value: 300, label: 'Light' },
  { value: 400, label: 'Regular' },
  { value: 500, label: 'Medium' },
  { value: 600, label: 'Semibold' },
]
const sizes = [
  { token: '--fs-xs', px: '11px', use: 'Captions, badges, helper text' },
  { token: '--fs-sm', px: '13px', use: 'Body text in tables, forms and buttons' },
  { token: '--fs-md', px: '15px', use: 'Emphasised body text, card titles' },
  { token: '--fs-lg', px: '18px', use: 'Section headings' },
  { token: '--fs-xl', px: '24px', use: 'Page headings and big numbers' },
]
const navTabs = ['Dashboard', 'My Events', 'New Request', 'Drafts']
const manyTabs = ['Dashboard', 'Upcoming Events', 'Venue Catalogue', 'Venue Calendar', 'Equipment Catalogue', 'Reservations', 'My Assignments', 'Maintenance Status']
const navTab = ref('Dashboard')
const manyTab = ref('Dashboard')
const open = ref(false)
const tab = ref('open')
const showAlert = ref(true)
const clicked = ref('')
const title = ref('')
const kind = ref('')
const desc = ref('')
</script>

<style scoped>
.page { max-width: 960px; margin: 0 auto; padding: var(--space-6) var(--space-5); }
.row { display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: center; }
.form { display: grid; gap: var(--space-4); }
.stack { display: grid; gap: var(--space-3); }
.note { color: var(--muted); font-size: var(--fs-sm); }
.shape { padding: var(--space-4) var(--space-5); background: var(--glass); border: 1px solid var(--hairline); color: var(--text); font-size: var(--fs-sm); }
.shape.chip { padding: var(--space-2) var(--space-4); }
.hover-demo:hover { background: rgba(255, 255, 255, .08); }
.type-card { margin-top: var(--space-3); }
.type-list { display: grid; gap: var(--space-3); }
.type-row { display: grid; grid-template-columns: 140px 1fr; align-items: baseline; gap: var(--space-4); }
.type-row code { justify-self: start; }
.sample { color: var(--text); }
.demo-h { margin: 0 0 var(--space-1); }
.navbar-demo { margin-bottom: var(--space-3); border: 1px solid var(--hairline); border-radius: var(--radius); background: var(--void); overflow: hidden; }
code { padding: 1px 6px; border-radius: 6px; background: var(--glass-strong); font-size: var(--fs-xs); }
</style>
