<template>
  <!-- Full cosmic scene on the public pages; a calm static one inside the app, where people read data. -->
  <CosmicBackdrop v-if="isPublicPage" />
  <CalmBackdrop v-else />
  <NotificationBell v-if="showFloatingBell" />
  <div class="app-layer">
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import CalmBackdrop from './components/shared/CalmBackdrop.vue'
import CosmicBackdrop from './components/shared/CosmicBackdrop.vue'
import NotificationBell from './components/shared/NotificationBell.vue'
import { session } from './store/session.js'

// The login page has its own header and the full backdrop; the bell is for the signed-in app.
const route = useRoute()
const isPublicPage = computed(() => route.name === 'login')
// The /dev/ui catalogue shows the bell itself, in its navbar demo.
const isDevPage = computed(() => route.name === 'dev-ui')
// The dashboard shell carries its own bell in the top bar; other signed-in pages float it in the corner.
const showFloatingBell = computed(
  () => session.isAuthenticated && !isPublicPage.value && !isDevPage.value && route.name !== 'dashboard',
)
</script>

<style scoped>
/* Every route renders above the fixed starfield */
.app-layer { position: relative; z-index: 1; }

.page-enter-active,
.page-leave-active {
  transition: opacity .45s var(--ease-out), transform .45s var(--ease-out);
}
.page-enter-from { opacity: 0; transform: translateY(12px); }
.page-leave-to { opacity: 0; transform: translateY(-8px); }

@media (prefers-reduced-motion: reduce) {
  .page-enter-active, .page-leave-active { transition: none; }
}
</style>
