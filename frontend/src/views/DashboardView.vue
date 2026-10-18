<template>
  <div class="shell">
    <aside class="sidebar">
      <AppLogo dark />

      <nav class="nav">
        <div
          v-for="tab in currentData.tabs"
          :key="tab"
          class="nav-item"
          :class="{ active: activeTab === tab }"
          @click="selectTab(tab)"
        >
          {{ tab }}
        </div>
      </nav>

      <div class="sidebar-footer">
        <div class="role-label">Signed in as {{ session.name }} ({{ currentData.label }})</div>
        <button class="logout-btn" @click="logout">Log out</button>
      </div>
    </aside>

    <main class="content">
      <h2>{{ activeTab }}</h2>

      <!-- Each tab renders its own feature-folder component. Anything not -->
      <!-- listed here has no folder yet — that's an honest scope signal,   -->
      <!-- not a bug, for tabs not built this sprint.                      -->
      <SafetyDashboard v-if="activeTab === 'Dashboard' && session.role === 'safety'" />
      <LeadDashboard
        v-else-if="activeTab === 'Dashboard' && session.role === 'coordinatorlead'"
        @open-tab="activeTab = $event"
      />
      <AttendeeHome
        v-else-if="activeTab === 'Dashboard' && session.role === 'attendee'"
        @open-tab="activeTab = $event"
      />
      <template v-else-if="activeTab === 'Dashboard'">
        <TechReverificationQueue v-if="session.role === 'techsupport'" />
        <DashboardHome :cards="currentData.cards" />
      </template>
      <VenueCatalogue v-else-if="activeTab === 'Venue Catalogue'" />
      <VenueCalendar
        v-else-if="activeTab === 'Venue Calendar'"
        :focus-venue="calendarFocus.venueId"
        :focus-at="calendarFocus.at"
      />
      <UnavailabilityList v-else-if="activeTab === 'Unavailability'" />
      <BookingRequests v-else-if="activeTab === 'Booking Requests'" />
      <BrowseEvents v-else-if="activeTab === 'Browse Events'" />
      <CreateEvent v-else-if="activeTab === 'New Request'" />
      <UpcomingEventsCalendar v-else-if="activeTab === 'Upcoming Events'"/>
      <EquipmentCatalogue v-else-if="activeTab === 'Equipment Catalogue'" />
      <AssignedEvents v-else-if="activeTab === 'Assigned Events'" />
      <ReviewQueue v-else-if="activeTab === 'Review Queue'" />
      <CoordinatorAssignments v-else-if="activeTab === 'Assignments'" />
      <SafetyReviews v-else-if="activeTab === 'Safety Reviews'" />
      <DraftsList v-else-if="activeTab === 'Drafts'" @edit-draft="activeTab = 'New Request'" />
      <MyEvents v-else-if="activeTab === 'My Events'" @create="activeTab = 'New Request'" />
      <MyRegistrations v-else-if="activeTab === 'My Registrations'" />
      <Profile v-else-if="activeTab === 'Profile'" />

      <div class="not-built" v-else>
        This tab isn't built yet for this sprint — only Dashboard{{ hasVenueTab ? ', Venue Catalogue' : '' }}{{ hasCalendarTab ? ', Venue Calendar' : '' }}{{ hasUnavailabilityTab ? ', Unavailability' : '' }}{{ hasAssignedTab ? ', Assigned Events' : '' }}{{ hasEventsTab ? ', Browse Events' : '' }}{{ hasNewRequestTab ? ', New Request' : '' }}{{ hasEquipmentTab ? ', Equipment Catalogue' : '' }}{{ hasMyEventsTab ? ', My Events' : '' }}{{ hasRegistrationsTab ? ', My Registrations' : '' }}{{ hasProfileTab ? ', Profile' : '' }} are functional.
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { signOut } from 'firebase/auth'
import AppLogo from '../components/shared/AppLogo.vue'
import DashboardHome from '../features/dashboard/DashboardHome.vue'
import AttendeeHome from '../features/dashboard/AttendeeHome.vue'
import TechReverificationQueue from '../features/dashboard/TechReverificationQueue.vue'
import VenueCatalogue from '../features/venue-catalogue/VenueCatalogue.vue'
import VenueCalendar from '../features/venue-calendar/VenueCalendar.vue'
import UnavailabilityList from '../features/unavailability/UnavailabilityList.vue'
import BookingRequests from '../features/booking-requests/BookingRequests.vue'
import BrowseEvents from '../features/browse-events/BrowseEvents.vue'
import CreateEvent from '../features/create-event/CreateEvent.vue'
import { roles } from '../config/roles.js'
import { auth } from '../firebase.js'
import { session, logoutSession } from '../store/session.js'
import UpcomingEventsCalendar from '../features/event-calendar/EventCalendar.vue'
import EquipmentCatalogue from '../features/equipment-catalogue/EquipmentCatalogue.vue'
import AssignedEvents from '../features/assigned-events/AssignedEvents.vue'
import ReviewQueue from '../features/review-queue/ReviewQueue.vue'
import CoordinatorAssignments from '../features/assignments/CoordinatorAssignments.vue'
import DraftsList from '../features/drafts/DraftsList.vue'
import MyEvents from '../features/my-events/MyEvents.vue'
import MyRegistrations from '../features/my-registrations/MyRegistrations.vue'
import Profile from '../features/profile/Profile.vue'
import SafetyDashboard from '../features/safety-reviews/SafetyDashboard.vue'
import LeadDashboard from '../features/lead-dashboard/LeadDashboard.vue'
import SafetyReviews from '../features/safety-reviews/SafetyReviews.vue'
import { draftEditor } from '../store/draftEditor.js'

const router = useRouter()
const route = useRoute()
// session.role is briefly null during logout (logoutSession() runs before
// the router finishes navigating away from this still-mounted view), so
// this falls back to an empty role rather than crashing on
// "Cannot read properties of undefined" for that one render.
const currentData = computed(() => roles[session.role] ?? { tabs: [], cards: [], label: '' })

function focusFromRoute() {
  return {
    venueId: typeof route.query.venue === 'string' ? route.query.venue : '',
    at: typeof route.query.at === 'string' ? route.query.at : ''
  }
}

function tabFromRoute() {
  const requested = route.query.tab
  if (typeof requested === 'string' && (roles[session.role]?.tabs || []).includes(requested)) return requested
  return 'Dashboard'
}

const activeTab = ref(tabFromRoute())
const calendarFocus = ref(focusFromRoute())

const hasVenueTab = computed(() => currentData.value.tabs.includes('Venue Catalogue'))
const hasCalendarTab = computed(() => currentData.value.tabs.includes('Venue Calendar'))
const hasUnavailabilityTab = computed(() => currentData.value.tabs.includes('Unavailability'))
const hasAssignedTab = computed(() => currentData.value.tabs.includes('Assigned Events'))
const hasEventsTab = computed(() => currentData.value.tabs.includes('Browse Events'))
const hasNewRequestTab = computed(() => currentData.value.tabs.includes('New Request'))
const hasEquipmentTab = computed(() => currentData.value.tabs.includes('Equipment Catalogue'))
const hasMyEventsTab = computed(() => currentData.value.tabs.includes('My Events'))
const hasRegistrationsTab = computed(() => currentData.value.tabs.includes('My Registrations'))
const hasProfileTab = computed(() => currentData.value.tabs.includes('Profile'))

// Coming back from the event detail page (e.g. after discarding a draft)
// lands on a specific tab via ?tab= instead of always resetting to Dashboard.
onMounted(syncFromRoute)
watch(() => [route.query.tab, route.query.venue, route.query.at], syncFromRoute)

function syncFromRoute() {
  const requestedTab = route.query.tab
  if (requestedTab === 'Venue Calendar') calendarFocus.value = focusFromRoute()
  if (typeof requestedTab === 'string' && currentData.value.tabs.includes(requestedTab)) {
    activeTab.value = requestedTab
  }
  if (requestedTab === 'Venue Calendar') {
    nextTick(() => document.querySelector('.content')?.scrollTo(0, 0))
  }
}

function selectTab(tab) {
  if (tab === activeTab.value) return
  // The New Request form isn't a route, so this click is the only place that
  // can intercept an in-app "navigate away" while it has unsaved changes.
  if (draftEditor.isDirty && !window.confirm('You have unsaved changes. Leave without saving?')) {
    return
  }
  calendarFocus.value = { venueId: '', at: '' }
  activeTab.value = tab
  router.replace({ name: 'dashboard', query: { tab } })
}

async function logout() {
  await signOut(auth)
  logoutSession()
  router.replace('/login')
}
</script>

<style scoped>
.shell {
  display: flex;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.sidebar {
  width: 240px;
  flex-shrink: 0;
  height: 100%;
  min-height: 0;
  background: rgba(11, 5, 26, .55);
  border-right: 1px solid var(--hairline);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  color: var(--text);
  padding: 24px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow: hidden;
}

.sidebar :deep(.logo) { flex-shrink: 0; }

.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
}
.nav-item {
  position: relative;
  padding: 11px 14px;
  border-radius: 10px;
  color: var(--body);
  cursor: pointer;
  transition: background .35s var(--ease-out), color .35s var(--ease-out);
}
.nav-item.active {
  background: linear-gradient(90deg, rgba(124, 77, 255, .3), rgba(124, 77, 255, .06));
  color: var(--text);
  box-shadow: inset 0 0 0 1px rgba(167, 139, 250, .3);
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 22%;
  bottom: 22%;
  width: 2px;
  border-radius: 2px;
  background: var(--iris-soft);
  box-shadow: 0 0 10px var(--iris);
}
.nav-item:hover:not(.active) { background: rgba(255, 255, 255, .04); color: var(--text); }

.sidebar-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 14px;
  border-top: 1px solid var(--hairline);
}
.role-label { font-size: 11px; line-height: 1.6; color: var(--muted); }
.logout-btn {
  background: none;
  border: 1px solid var(--hairline);
  color: var(--body);
  border-radius: 999px;
  padding: 9px 0;
  font-size: 13px;
  font-family: 'Inter', sans-serif;
  cursor: pointer;
  transition: background .35s var(--ease-out), color .35s var(--ease-out),
              border-color .35s var(--ease-out);
}
.logout-btn:hover {
  background: rgba(167, 139, 250, .1);
  border-color: rgba(167, 139, 250, .4);
  color: var(--text);
}

.content {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 38px 40px;
}
.content h2 {
  margin: 0 0 26px;
  font-size: 22px;
  font-weight: 400;
  letter-spacing: -.01em;
}

.not-built {
  color: var(--muted);
  font-size: 14px;
  background: var(--glass);
  border: 1px dashed var(--hairline);
  border-radius: 14px;
  padding: 26px;
}

@media (max-width: 720px) {
  .shell { flex-direction: column; }
  .sidebar {
    width: 100%;
    height: auto;
    max-height: 46vh;
    border-right: none;
    border-bottom: 1px solid var(--hairline);
  }
  .content { padding: 28px 22px; }
}
</style>
