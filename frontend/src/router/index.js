import { createRouter, createWebHistory } from 'vue-router'
import LandingView from '../views/LandingView.vue'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import EventDetail from '../features/event-detail/EventDetail.vue'
import EventRegistrations from '../features/event-detail/EventRegistrations.vue'
import EventRegistrationSettings from '../features/event-detail/EventRegistrationSettings.vue'
import RegistrationDetail from '../features/my-registrations/RegistrationDetail.vue'
import EventVenueSelect from '../features/venue-request/EventVenueSelect.vue'
import BrowseEvent from '../features/browse-events/BrowseEvent.vue'
import EventReadiness from '../features/event-detail/EventReadiness.vue'
import EventEquipmentCheck from '../features/equipment-catalogue/EventEquipmentCheck.vue'
import EquipmentDetail from '../features/equipment-catalogue/EquipmentDetail.vue'
import NotificationsPage from '../features/notifications/NotificationsPage.vue'
import NotificationFollow from '../features/notifications/NotificationFollow.vue'
import { session } from '../store/session.js'

// Component catalogue for developers; not registered in production builds.
const devRoutes = import.meta.env.DEV
  ? [{ path: '/dev/ui', name: 'dev-ui', component: () => import('../views/UiShowcase.vue') }]
  : []

const router = createRouter({
  history: createWebHistory(),
  routes: [
    ...devRoutes,
    { path: '/', name: 'landing', component: LandingView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/app', name: 'dashboard', component: DashboardView, meta: { requiresAuth: true } },
    {
      path: '/app/notifications',
      name: 'notifications',
      component: NotificationsPage,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/notifications/:id',
      name: 'notification-follow',
      component: NotificationFollow,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/events/:id',
      name: 'event-detail',
      component: EventDetail,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/events/:id/registrations',
      name: 'event-registrations',
      component: EventRegistrations,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/events/:id/registration-settings',
      name: 'event-registration-settings',
      component: EventRegistrationSettings,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/registrations',
      redirect: { path: '/app', query: { tab: 'My Registrations' } },
    },
    {
      path: '/app/registrations/:id',
      name: 'registration-detail',
      component: RegistrationDetail,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/browse/:id',
      name: 'browse-event',
      component: BrowseEvent,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/events/:id/readiness',
      name: 'event-readiness',
      component: EventReadiness,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/events/:id/equipment',
      name: 'event-equipment',
      component: EventEquipmentCheck,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/equipment/:id',
      name: 'equipment-detail',
      component: EquipmentDetail,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/events/:id/venues',
      name: 'event-venue-select',
      component: EventVenueSelect,
      meta: { requiresAuth: true }
    },
    {
      path: '/app/venues/bookings/:id',
      redirect: (to) => ({
        name: 'dashboard',
        query: { tab: 'Booking Requests', booking: String(to.params.id) }
      })
    },
    {
      path: '/app/venues/:id/calendar',
      redirect: (to) => ({
        name: 'dashboard',
        query: {
          tab: 'Venue Calendar',
          venue: String(to.params.id),
          ...(typeof to.query.at === 'string' ? { at: to.query.at } : {})
        }
      })
    }
  ]
})

// Every request is also independently verified server-side (401 without a
// valid Firebase token) — this guard only covers front-end navigation, so a
// signed-out user never even sees a protected view render.
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !session.isAuthenticated) {
    return { name: 'login' }
  }
  // An already-signed-in user hitting /login goes straight back to their
  // session instead of being shown the login form again.
  if (to.name === 'login' && session.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
