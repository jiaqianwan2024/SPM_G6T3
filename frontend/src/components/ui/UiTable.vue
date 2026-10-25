<template>
  <UiEmptyState v-if="!rows.length" :title="emptyTitle" :hint="emptyHint" />
  <div v-else class="wrap">
    <table>
      <thead>
        <tr><th v-for="c in columns" :key="c.key" scope="col">{{ c.label }}</th></tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="row[rowKey] ?? i">
          <!-- Override a cell with <template #cell-<key>="{ row, value }">. -->
          <td v-for="c in columns" :key="c.key">
            <slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]">{{ row[c.key] }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import UiEmptyState from './UiEmptyState.vue'

// columns: [{ key, label }]. rows: array of objects.
defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  rowKey: { type: String, default: 'id' },
  emptyTitle: { type: String, default: 'Nothing here yet' },
  emptyHint: { type: String, default: '' },
})
</script>

<style scoped>
.wrap { overflow-x: auto; border: 1px solid var(--hairline); border-radius: var(--radius); background: var(--glass); }
table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
th {
  position: sticky;
  top: 0;
  padding: var(--space-3) var(--space-4);
  text-align: left;
  font-size: var(--fs-xs);
  font-weight: 500;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--muted);
  background: var(--deep);
  border-bottom: 1px solid var(--hairline);
}
td { padding: var(--space-3) var(--space-4); color: var(--body); border-bottom: 1px solid var(--hairline); }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: var(--glass-strong); }
</style>
