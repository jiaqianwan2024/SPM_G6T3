<template>
  <header class="topbar">
    <button type="button" class="brand" aria-label="ConnectSphere, go to the dashboard" @click="$emit('select', 'Dashboard')">
      <AppLogo dark />
    </button>

    <nav class="nav" aria-label="Main">
      <button
        v-for="tab in tabs"
        :key="tab"
        type="button"
        class="nav-item"
        :class="{ active: activeTab === tab }"
        :aria-current="activeTab === tab ? 'page' : undefined"
        @click="$emit('select', tab)"
      >
        {{ tab }}
      </button>
    </nav>

    <div class="top-actions">
      <!-- demo: a static bell (no API polling); the profile menu is the real one, fed sample data. -->
      <button v-if="demo" type="button" class="icon-btn" aria-label="Notifications">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3.5c-2.9 0-5.1 2.2-5.1 5.2v3.1c0 .6-.2 1.2-.6 1.7l-1.1 1.4c-.6.8 0 2 1 2h11.6c1 0 1.6-1.2 1-2l-1.1-1.4c-.4-.5-.6-1.1-.6-1.7V8.7c0-3-2.2-5.2-5.1-5.2z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
          <path d="M10.2 19.5a1.9 1.9 0 0 0 3.6 0" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
        </svg>
      </button>
      <NotificationBell v-else inline />

      <div class="profile" @keydown.esc="menuOpen = false">
        <button
          type="button"
          class="icon-btn avatar"
          data-testid="profile-menu-button"
          aria-haspopup="menu"
          :aria-expanded="menuOpen"
          aria-label="Account menu"
          @click="menuOpen = !menuOpen"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="8.5" r="3.6" fill="none" stroke="currentColor" stroke-width="1.5" />
            <path d="M4.6 19.5c.9-3.4 3.9-5.2 7.4-5.2s6.5 1.8 7.4 5.2" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
        </button>

        <div v-if="menuOpen" class="backdrop" @click="menuOpen = false"></div>
        <ProfileMenu v-if="menuOpen" class="menu" :sample="demo ? DEMO_PROFILE : null" @logout="logout" />
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import AppLogo from '../shared/AppLogo.vue'
import NotificationBell from '../shared/NotificationBell.vue'
import ProfileMenu from '../shared/ProfileMenu.vue'

// The app's top navbar: logo left, role tabs in the middle, bell and profile right.
// `demo` swaps the live bell for a static one and feeds the profile card sample data (the /dev/ui catalogue).
defineProps({
  tabs: { type: Array, default: () => [] },
  activeTab: { type: String, default: '' },
  demo: { type: Boolean, default: false },
})
const emit = defineEmits(['select', 'logout'])

const menuOpen = ref(false)

const DEMO_PROFILE = {
  userName: 'Alice Tan',
  email: 'organiser@connectsphere.com',
  role: 'organiser',
  organisationId: 'demo',
  organisationName: 'Apex Partners',
}

function logout() {
  menuOpen.value = false
  emit('logout')
}
</script>

<style scoped>
/* ---------- Top navbar ---------- */
.topbar {
  flex-shrink: 0;
  height: 64px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-5);
  /* PAGE EDGES (--edge-left / --edge-right in main.css): the logo starts at the left edge and the
     profile button ends at the right edge, the same lines the page content uses. Do not change. */
  padding: 0 var(--edge-right) 0 var(--edge-left);
  /* No fill of its own: the bar shares the page background with the content below. */
  position: relative;
  z-index: 10;
}

.brand {
  display: flex;
  align-items: center;
  padding: 0;
  background: none;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
}
.brand:focus-visible { outline: none; box-shadow: var(--focus-ring); }

/* Tabs sit in the middle. Roles with many tabs scroll sideways rather than wrapping;
   the auto margins centre them when they fit and never clip the first tab when they don't. */
.nav {
  min-width: 0;
  display: flex;
  align-items: stretch;
  align-self: stretch;
  gap: var(--space-1);
  overflow-x: auto;
  scrollbar-width: none;
}
.nav::-webkit-scrollbar { display: none; }
.nav-item:first-child { margin-left: auto; }
.nav-item:last-child { margin-right: auto; }

.nav-item {
  position: relative;
  flex-shrink: 0;
  align-self: stretch;
  padding: 0 var(--space-4);
  border: none;
  background: none;
  font: 400 var(--fs-sm) var(--font);
  letter-spacing: .01em;
  white-space: nowrap;
  color: var(--body);
  cursor: pointer;
  transition: color .3s var(--ease-out);
}
/* The active tab is marked by an underline sitting on the bar's bottom edge. */
.nav-item::after {
  content: '';
  position: absolute;
  left: var(--space-4);
  right: var(--space-4);
  bottom: 0;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: var(--halo);
  transform: scaleX(0);
  transition: transform .3s var(--ease-out);
}
.nav-item:hover { color: var(--text); }
.nav-item.active { color: var(--text); font-weight: 500; }
.nav-item.active::after { transform: scaleX(1); }
.nav-item:focus-visible { outline: none; color: var(--text); box-shadow: inset 0 0 0 2px var(--iris-soft); border-radius: var(--radius); }

.top-actions { flex-shrink: 0; display: flex; align-items: center; gap: var(--space-2); }

.icon-btn {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  padding: 0;
  background: none;
  border: none;
  border-radius: var(--radius);
  color: var(--icon);
  cursor: pointer;
  transition: background .3s var(--ease-out);
}
.icon-btn svg { width: 24px; height: 24px; }
.icon-btn:hover { background: rgba(255, 255, 255, .08); }
.icon-btn:focus-visible { outline: none; box-shadow: var(--focus-ring); }

/* ---------- Profile menu ---------- */
.profile { position: relative; }
.backdrop { position: fixed; inset: 0; z-index: 59; }
.menu { position: absolute; top: 50px; right: 0; z-index: 60; }

@media (max-width: 720px) {
  .topbar { height: 56px; padding: 0 var(--space-2) 0 var(--space-4); gap: var(--space-2); }
  /* The mark alone on a phone; the name returns on wider screens. */
  .brand :deep(.wordmark) { display: none; }
}
</style>
