<template>
  <div class="page">
    <PageHeader title="UI components" subtitle="Dev-only catalogue. Every shared primitive in its main states." />

    <SectionBlock title="Navbar">
      <p class="note">
        The app's top bar (<code>AppNavbar</code>): logo left, the role's tabs in the middle, notifications and
        profile right. Click the tabs to see the active underline. The bell is static here; the profile icon opens the menu.
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

    <SectionBlock title="Profile card">
      <p class="note">
        <code>ProfileMenu</code>: the panel behind the navbar's profile icon, made of <code>ProfileCard</code> and
        a Log Out row. Each detail is a white icon followed by its value: role, email, organisation, in that order.
        Long values wrap, with the icon staying beside the first line. The panel is 280px wide with
        <code>--profile-bg</code> as its background. In the app the card loads the signed-in user; pass
        <code>sample</code> to show fixed data, as here. Left: typical values. Right: very long values.
      </p>
      <div class="row top">
        <ProfileMenu :sample="profileSample" />
        <ProfileMenu :sample="profileLong" />
      </div>
    </SectionBlock>

    <SectionBlock title="Notification card">
      <p class="note">
        <code>NotificationMenu</code>: the panel behind the bell, built like the profile card (400px wide,
        <code>--profile-bg</code>). A slim action row on top has See all, Mark all read (disabled when nothing is
        unread) and Clear all (disabled when the panel is empty). Each row is a white bold title, the description, and the
        time on a 12-hour clock (Singapore time, no zone label); unread rows have a small dot at the left. Hovering a row
        swaps its time for a bin button that deletes it from the bell (always shown on touch screens). Long lists scroll
        inside the panel with the action row pinned. The component only displays what it is given.
      </p>
      <div class="cards">
        <figure>
          <NotificationMenu :items="notifications" />
          <figcaption>With unread and read notifications</figcaption>
        </figure>
        <figure>
          <NotificationMenu :items="notifications.map((n) => ({ ...n, isRead: true }))" />
          <figcaption>All read (Mark all read disabled)</figcaption>
        </figure>
        <figure>
          <NotificationMenu :items="longTextNotifications" />
          <figcaption>Long title and description wrap and clamp</figcaption>
        </figure>
        <figure>
          <NotificationMenu :items="manyNotifications" />
          <figcaption>Many notifications scroll, action row pinned</figcaption>
        </figure>
        <figure>
          <NotificationMenu :items="[]" />
          <figcaption>Empty (Clear all disabled)</figcaption>
        </figure>
        <figure>
          <NotificationMenu loading />
          <figcaption>Loading</figcaption>
        </figure>
        <figure>
          <NotificationMenu error="Could not load notifications. Please try again." />
          <figcaption>Error</figcaption>
        </figure>
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
import NotificationMenu from '../components/shared/NotificationMenu.vue'
import ProfileMenu from '../components/shared/ProfileMenu.vue'
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
const profileSample = {
  userName: 'Alice Tan',
  email: 'organiser@connectsphere.com',
  role: 'organiser',
  organisationId: 'demo',
  organisationName: 'Apex Partners',
}
const profileLong = {
  userName: 'Alexandria Bartholomew-Fitzgerald',
  email: 'alexandria.bartholomew-fitzgerald@events.connectsphere.example.com',
  role: 'coordinatorlead',
  organisationId: 'demo',
  organisationName: 'The International Association of Independent Event Producers',
}
const notifications = [
  { notificationId: 'n1', isRead: false, title: 'Clarification requested', body: 'Your coordinator asked you to confirm the expected attendance for Partner Networking Night.', createdAt: '2026-10-26T01:40:00Z' },
  { notificationId: 'n2', isRead: false, title: 'Request approved', body: 'AI in Events Summit has been approved.', createdAt: '2026-10-25T09:15:00Z' },
  { notificationId: 'n3', isRead: true, title: 'Venue confirmed', body: 'Marina Hall A is booked for 12 Nov, 18:00 – 21:00.', createdAt: '2026-10-23T04:05:00Z' },
]
// A long list: the panel stops at its max height and the list scrolls, with the action row staying on top.
const longTextNotifications = [
  {
    notificationId: 'long-1',
    isRead: false,
    title: 'Change request declined for the Beacon Q4 Showcase layout and seating plan',
    body: 'The venue cannot fit the banquet layout you asked for at the current expected attendance, so the coordinator declined the change and kept the theatre layout. Please review the capacity options and raise a new request if you still need to change it.',
    createdAt: '2026-10-26T01:40:00Z',
  },
  { notificationId: 'long-2', isRead: true, title: 'Venue confirmed', body: 'Marina Hall A is booked.', createdAt: '2026-10-25T09:15:00Z' },
]
const manyNotifications = Array.from({ length: 12 }, (_, i) => ({
  notificationId: `many-${i}`,
  isRead: i > 3,
  title: ['Clarification requested', 'Request approved', 'Venue confirmed', 'Equipment reserved'][i % 4],
  body: `Update ${i + 1} for the Partner Networking Night event.`,
  createdAt: `2026-10-${String(25 - (i % 20)).padStart(2, '0')}T09:15:00Z`,
}))
const navTabs = ['Dashboard', 'My Events', 'New Request']
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
/* Full width with the app's own page edges (see frontend/CLAUDE.md), so components render at the sizes they
   have in the app. This page scrolls with the window, so it gives back the scrollbar space itself. */
.page { padding: 38px calc(var(--edge-right) - var(--scrollbar-w)) 38px var(--edge-left); }
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
.top { align-items: flex-start; }
.cards { display: flex; flex-wrap: wrap; align-items: flex-start; gap: var(--space-5); }
.cards figure { margin: 0; display: grid; gap: var(--space-2); }
.cards figcaption { font-size: var(--fs-xs); color: var(--muted); }
.sub { margin: var(--space-5) 0 var(--space-2); font-size: var(--fs-md); font-weight: 500; }
.navbar-demo { margin-bottom: var(--space-3); border: 1px solid var(--hairline); border-radius: var(--radius); background: var(--void); overflow: hidden; }
code { padding: 1px 6px; border-radius: 6px; background: var(--glass-strong); font-size: var(--fs-xs); }
</style>
