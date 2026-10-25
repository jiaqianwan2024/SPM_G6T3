<template>
  <section v-if="rows.length" class="queue" data-testid="tech-reverification-queue">
    <h3>Needs re-verification</h3>
    <article
      v-for="row in rows"
      :key="row.reservationId"
      class="row"
      :data-testid="`tech-reverification-${row.reservationId}`"
    >
      <strong>{{ row.equipmentName || row.equipmentId }}</strong>
      <span>{{ row.quantity }} held for {{ row.eventId }}</span>
      <p v-if="row.reverificationNote">{{ row.reverificationNote }}</p>
    </article>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getEquipmentQueue } from '../../api/equipmentService.js'

const rows = ref([])

onMounted(async () => {
  try {
    const { data } = await getEquipmentQueue()
    rows.value = data
  } catch {
    rows.value = []
  }
})
</script>

<style scoped>
.queue {
  margin: 0 0 16px;
  display: grid;
  gap: 10px;
}
.queue h3 { margin: 0; font-size: 1rem; }
.row {
  padding: 12px 14px;
  border-radius: var(--radius);
  background: #fef3c7;
  color: #92400e;
}
.row p { margin: 6px 0 0; }
</style>
