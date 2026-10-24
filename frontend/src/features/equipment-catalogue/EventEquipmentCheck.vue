<template>
  <div class="event-equipment-check">
    <button type="button" class="btn btn-ghost back" @click="router.push({ path: '/app', query: { tab: 'Upcoming Events' } })">
      ← Upcoming events
    </button>
    <header class="page-head">
      <p class="eyebrow">Equipment</p>
      <h1>{{ title }}</h1>
      <p class="lede">Check whether the stock can cover this event, then accept and reserve each request.</p>
      <button type="button" class="btn btn-ghost small" @click="router.push(`/app/events/${eventId}`)">Open the event</button>
    </header>
    <RequestAvailability :event-id="eventId" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RequestAvailability from './RequestAvailability.vue'
import { getEvent } from '../../api/eventService.js'

// SPM-4 AC7: where technical support land when they open an event from the upcoming-events queue.
const route = useRoute()
const router = useRouter()
const eventId = computed(() => String(route.params.id))
const eventName = ref('')
const title = computed(() => eventName.value || `Event ${eventId.value}`)

onMounted(async () => {
  try {
    const { data } = await getEvent(eventId.value)
    eventName.value = data.eventName
  } catch {
    // Non-fatal - the page falls back to the event id.
  }
})
</script>

<style scoped>
.event-equipment-check {
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 32px 48px;
}
.back { margin: 0 0 18px -18px; padding-left: 18px; }
.page-head { margin-bottom: 18px; }
.page-head h1 { margin: 6px 0 8px; font-size: 28px; font-weight: 500; letter-spacing: -.02em; }
.lede { margin: 0 0 12px; color: var(--body); font-size: 14px; }
</style>
