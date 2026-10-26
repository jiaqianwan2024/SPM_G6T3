<template>
  <div class="shell">
    <AppNavbar :tabs="tabs" :active-tab="activeTab" @select="$emit('select', $event)" @logout="$emit('logout')" />

    <!-- `.content` is also the scroll container other code scrolls to top. -->
    <main class="content">
      <slot />
    </main>
  </div>
</template>

<script setup>
import AppNavbar from './AppNavbar.vue'

defineProps({
  tabs: { type: Array, default: () => [] },
  activeTab: { type: String, default: '' },
})
defineEmits(['select', 'logout'])
</script>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.content {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  /* PAGE EDGES (--edge-left / --edge-right in main.css): do not change this horizontal padding.
     The scrollbar space is always reserved, so the right edge is steady, and the padding gives
     that space back so the content ends exactly at --edge-right. */
  scrollbar-gutter: stable;
  padding: 38px calc(var(--edge-right) - var(--scrollbar-w)) 38px var(--edge-left);
}

@media (max-width: 720px) {
  .content { scrollbar-gutter: auto; padding: 24px var(--space-4); }
}
</style>
