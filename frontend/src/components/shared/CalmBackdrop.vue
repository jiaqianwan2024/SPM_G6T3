<template>
  <div class="calm" aria-hidden="true"></div>
</template>

<style scoped>
/* The signed-in app's background: static, with only a faint glow at the top.
   No animation or canvas, so tables and queues stay easy to read and cheap to paint. */
.calm {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(90% 45% at 50% 0%, rgba(124, 77, 255, .14), transparent 70%),
    linear-gradient(180deg, #0F0724 0%, var(--void) 100%);
}
</style>
