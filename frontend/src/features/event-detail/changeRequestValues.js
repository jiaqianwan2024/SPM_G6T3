import { formatSgt } from '../../utils/datetime.js'

export const DATETIME_FIELDS = ['proposedStartAt', 'proposedEndAt']

// A change request's current or proposed value as people read it. `names` maps
// equipmentId -> catalogue name, for equipment lines (SPM-85 AC5).
export function formatChangeValue(field, value, names = {}) {
  if (field === 'equipmentLines') {
    if (!value?.length) return 'None'
    return value.map((line) => `${line.quantity} × ${names[line.equipmentId] || line.equipmentId}`).join(', ')
  }
  if (value === null || value === undefined || value === '') return 'Not set'
  if (DATETIME_FIELDS.includes(field)) return formatSgt(value) || String(value)
  return String(value)
}

export function errorText(err, fallback) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(' ')
  return detail?.message || fallback
}
