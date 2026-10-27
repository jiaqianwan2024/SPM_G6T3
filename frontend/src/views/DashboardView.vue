<template>
  <AppShell
    :tabs="currentData.tabs"
    :active-tab="activeTab"
    @select="selectTab"
    @logout="logout"
  >
      <!-- Each tab renders its own feature-folder component. Anything not -->
      <!-- listed here has no folder yet — that's an honest scope signal,   -->
      <!-- not a bug, for tabs not built this sprint.                      -->
      <SafetyDashboard v-if="activeTab === 'Dashboard' && session.role === 'safety'" />
      <OrganiserDashboard
        v-else-if="activeTab === 'Dashboard' && session.role === 'organiser'"
        @open-tab="selectTab"
      />
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
        :focus-from="calendarFocus.from"
        :focus-to="calendarFocus.to"
      />
      <UnavailabilityList v-else-if="activeTab === 'Unavailability'" />
      <BookingRequests v-else-if="activeTab === 'Booking Requests'" />
      <BrowseEvents v-else-if="activeTab === 'Browse Events'" />
      <CreateEvent v-else-if="activeTab === 'New Request'" />
      <UpcomingEventsQueue v-else-if="activeTab === 'Upcoming Events'"/>
      <EquipmentCatalogue v-else-if="activeTab === 'Equipment Catalogue'" />
      <AssignedEvents v-else-if="activeTab === 'Assigned Events'" />
      <ReviewQueue v-else-if="activeTab === 'Review Queue'" />
      <CoordinatorAssignments v-else-if="activeTab === 'Assignments'" />
      <SafetyReviews v-else-if="activeTab === 'Safety Reviews'" />
      <DraftsList v-else-if="activeTab === 'Drafts'" @edit-draft="activeTab = 'New Request'" />
      <MyEvents v-else-if="activeTab === 'My Events'" @create="activeTab = 'New Request'" />
      <MyRegistrations v-else-if="activeTab === 'My Registrations'" />

      <div class="not-built" v-else>
        This tab isn't built yet for this sprint — only Dashboard{{ hasVenueTab ? ', Venue Catalogue' : '' }}{{ hasCalendarTab ? ', Venue Calendar' : '' }}{{ hasUnavailabilityTab ? ', Unavailability' : '' }}{{ hasAssignedTab ? ', Assigned Events' : '' }}{{ hasEventsTab ? ', Browse Events' : '' }}{{ hasNewRequestTab ? ', New Request' : '' }}{{ hasEquipmentTab ? ', Equipment Catalogue' : '' }}{{ hasMyEventsTab ? ', My Events' : '' }}{{ hasRegistrationsTab ? ', My Registrations' : '' }} are functional.
      </div>
  </AppShell>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { signOut } from 'firebase/auth'
import AppShell from '../components/layout/AppShell.vue'
import DashboardHome from '../features/dashboard/DashboardHome.vue'
import OrganiserDashboard from '../features/dashboard/OrganiserDashboard.vue'
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
import UpcomingEventsQueue from '../features/upcoming-events/UpcomingEventsQueue.vue'
import EquipmentCatalogue from '../features/equipment-catalogue/EquipmentCatalogue.vue'
import AssignedEvents from '../features/assigned-events/AssignedEvents.vue'
import ReviewQueue from '../features/review-queue/ReviewQueue.vue'
import CoordinatorAssignments from '../features/assignments/CoordinatorAssignments.vue'
import DraftsList from '../features/drafts/DraftsList.vue'
import MyEvents from '../features/my-events/MyEvents.vue'
import MyRegistrations from '../features/my-registrations/MyRegistrations.vue'
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
    at: typeof route.query.at === 'string' ? route.query.at : '',
    from: typeof route.query.from === 'string' ? route.query.from : '',
    to: typeof route.query.to === 'string' ? route.query.to : ''
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
  calendarFocus.value = { venueId: '', at: '', from: '', to: '' }
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
.not-built {
  color: var(--muted);
  font-size: 14px;
  background: var(--glass);
  border: 1px dashed var(--hairline);
  border-radius: var(--radius);
  padding: 26px;
}
</style>
