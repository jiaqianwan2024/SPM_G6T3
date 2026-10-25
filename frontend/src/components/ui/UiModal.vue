<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @mousedown.self="$emit('close')">
      <div ref="dialog" class="dialog" role="dialog" aria-modal="true" :aria-labelledby="titleId"
           tabindex="-1" @keydown="onKeydown">
        <header class="head">
          <h3 :id="titleId">{{ title }}</h3>
          <button type="button" class="x" aria-label="Close" @click="$emit('close')">×</button>
        </header>
        <div class="body"><slot /></div>
        <footer v-if="$slots.footer" class="foot"><slot name="footer" /></footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { uid } from '../../composables/uid'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, required: true },
})
const emit = defineEmits(['close'])

const dialog = ref(null)
const titleId = uid('modal')
let opener = null

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Move focus in on open, and give it back to whatever opened the dialog on close.
watch(() => props.open, async (isOpen) => {
  if (isOpen) {
    opener = document.activeElement
    await nextTick()
    ;(dialog.value?.querySelector(FOCUSABLE) || dialog.value)?.focus()
  } else if (opener) {
    opener.focus?.()
    opener = null
  }
})

function onKeydown(e) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    emit('close')
    return
  }
  if (e.key !== 'Tab') return
  const items = [...dialog.value.querySelectorAll(FOCUSABLE)]
  if (!items.length) return e.preventDefault()
  const first = items[0]
  const last = items[items.length - 1]
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
}
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: var(--space-4);
  background: rgba(7, 3, 18, .7);
  backdrop-filter: blur(6px);
}
.dialog {
  width: min(520px, 100%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background: var(--deep);
  border: 1px solid var(--hairline);
  border-radius: var(--radius);
  box-shadow: 0 24px 80px rgba(0, 0, 0, .55);
}
.dialog:focus { outline: none; }
.head { display: flex; align-items: center; justify-content: space-between; padding: var(--space-4) var(--space-5); border-bottom: 1px solid var(--hairline); }
h3 { margin: 0; font-size: var(--fs-lg); }
.x { background: none; border: none; color: var(--body); font-size: 22px; line-height: 1; cursor: pointer; border-radius: var(--radius-sm); }
.x:hover { color: var(--text); }
.x:focus-visible { outline: none; box-shadow: var(--focus-ring); }
.body { padding: var(--space-5); overflow-y: auto; }
.foot { display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-4) var(--space-5); border-top: 1px solid var(--hairline); }
</style>
