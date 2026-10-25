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
  /* The 10px scrollbar (main.css) is always reserved, so the content's right edge is steady, and the
     padding gives that space back: the content ends 40px from the window edge, like the navbar's icons. */
  scrollbar-gutter: stable;
  padding: 38px 30px 38px 40px;
}

@media (max-width: 720px) {
  .content { scrollbar-gutter: auto; padding: 24px var(--space-4); }
}
</style>
