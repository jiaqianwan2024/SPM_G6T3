<template>
  <div class="profile-menu" role="dialog" aria-label="Your profile">
    <ProfileCard :sample="sample" />
    <button type="button" class="menu-item" @click="$emit('logout')">Log Out</button>
  </div>
</template>

<script setup>
import ProfileCard from './ProfileCard.vue'

// The panel behind the navbar's profile icon: the account card, then Log Out.
// It has no position of its own; the navbar places it. `sample` shows fixed data (the /dev/ui catalogue).
defineProps({ sample: { type: Object, default: null } })
defineEmits(['logout'])
</script>

<style scoped>
.profile-menu {
  width: 280px;
  max-width: calc(100vw - 32px);
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  background: var(--profile-bg);
  border: 1px solid rgba(167, 139, 250, .28);
  border-radius: var(--radius);
  box-shadow: 0 30px 90px rgba(4, 1, 12, .7), 0 0 60px rgba(124, 77, 255, .18);
}
.menu-item {
  margin-top: var(--space-1);
  padding: 9px var(--space-3);
  background: none;
  border: none;
  border-radius: var(--radius);
  text-align: left;
  font: var(--fs-sm) var(--font);
  color: var(--body);
  cursor: pointer;
  transition: background .25s var(--ease-out), color .25s var(--ease-out);
}
/* Same hover as the header icons: a soft white highlight. */
.menu-item:hover { background: rgba(255, 255, 255, .08); color: var(--text); }
.menu-item:focus-visible { outline: none; box-shadow: var(--focus-ring); }
</style>
