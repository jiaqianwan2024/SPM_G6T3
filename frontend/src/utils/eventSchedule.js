import { formatSgtDate, formatSgtTime, sgtDay } from './datetime.js'

// Plain-language date and time lines for an event's proposed window (SGT).
export function eventDateLabel(event) {
  const start = event.proposedStartAt
  const end = event.proposedEndAt
  if (!start && !end) return 'No date set yet'
  if (!start || !end) return 'Date incomplete'
  if (sgtDay(start) === sgtDay(end)) return formatSgtDate(start)
  return `${formatSgtDate(start)} – ${formatSgtDate(end)}`
}

export function eventTimeLabel(event) {
  const start = event.proposedStartAt
  const end = event.proposedEndAt
  if (!start || !end) return '—'
  return `${formatSgtTime(start)} – ${formatSgtTime(end)} SGT`
}
