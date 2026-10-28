// ConnectSphere's venues are in Singapore, so every time is shown and typed in
// Singapore time (SGT, UTC+8), whatever the viewer's computer is set to.
// The server stores and sends UTC; a time without a zone marker is UTC.
// Singapore has no daylight saving, so the offset is always +08:00.

export const SGT_ZONE = 'Asia/Singapore'
const OFFSET_MS = 8 * 60 * 60 * 1000
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// A server time (or Date) as a Date, or null when it is empty or not a time.
export function parseServerTime(value) {
  if (value === null || value === undefined || value === '') return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const text = String(value)
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(text)
  const date = new Date(hasZone ? text : `${text}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

// The Singapore wall-clock parts of a time.
function sgtParts(date) {
  const shifted = new Date(date.getTime() + OFFSET_MS)
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth(),
    day: shifted.getUTCDate(),
    hours: shifted.getUTCHours(),
    minutes: shifted.getUTCMinutes()
  }
}

const pad = (n) => String(n).padStart(2, '0')

// "19 Oct 2026"
export function formatSgtDate(value) {
  const date = parseServerTime(value)
  if (!date) return ''
  const p = sgtParts(date)
  return `${p.day} ${MONTHS[p.month]} ${p.year}`
}

// "10:00"
export function formatSgtTime(value) {
  const date = parseServerTime(value)
  if (!date) return ''
  const p = sgtParts(date)
  return `${pad(p.hours)}:${pad(p.minutes)}`
}

// "19 Oct 2026, 10:00 SGT"
export function formatSgt(value) {
  const date = parseServerTime(value)
  if (!date) return ''
  return `${formatSgtDate(date)}, ${formatSgtTime(date)} SGT`
}

// "19 Oct 2026, 10:00 AM": the Singapore time on a 12-hour clock, without the zone label.
export function formatSgt12h(value) {
  const date = parseServerTime(value)
  if (!date) return ''
  const p = sgtParts(date)
  const hour12 = p.hours % 12 || 12
  return `${formatSgtDate(date)}, ${hour12}:${pad(p.minutes)} ${p.hours < 12 ? 'AM' : 'PM'}`
}

// "19 Oct 2026, 10:00 to 12:00 SGT", or with both dates when it runs past midnight.
export function formatSgtRange(start, end) {
  const from = parseServerTime(start)
  const to = parseServerTime(end)
  if (!from || !to) return from ? formatSgt(from) : ''
  if (formatSgtDate(from) === formatSgtDate(to)) {
    return `${formatSgtDate(from)}, ${formatSgtTime(from)} to ${formatSgtTime(to)} SGT`
  }
  return `${formatSgtDate(from)}, ${formatSgtTime(from)} to ${formatSgtDate(to)}, ${formatSgtTime(to)} SGT`
}

// How long ago a time was: "just now", "45 minutes ago", "3 hours ago", "2 days ago".
export function formatTimeSince(value, now = new Date()) {
  const date = parseServerTime(value)
  if (!date) return ''
  const minutes = Math.floor((now.getTime() - date.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  const ago = (n, unit) => `${n} ${unit}${n === 1 ? '' : 's'} ago`
  if (minutes < 60) return ago(minutes, 'minute')
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return ago(hours, 'hour')
  return ago(Math.floor(hours / 24), 'day')
}

// The Singapore date of a time, as "YYYY-MM-DD" (what a date input holds).
export function sgtDay(value) {
  const date = parseServerTime(value)
  if (!date) return ''
  const p = sgtParts(date)
  return `${p.year}-${pad(p.month + 1)}-${pad(p.day)}`
}

// A server time as a datetime-local value ("YYYY-MM-DDTHH:mm") in Singapore time.
export function toSgtInput(value) {
  const date = parseServerTime(value)
  if (!date) return ''
  const p = sgtParts(date)
  return `${sgtDay(date)}T${pad(p.hours)}:${pad(p.minutes)}`
}

// A datetime-local value typed in Singapore time, as the server stores it: UTC
// without a zone marker ("YYYY-MM-DDTHH:mm:ss"), which every service accepts.
export function fromSgtInput(value) {
  if (!value) return ''
  const text = String(value)
  const withSeconds = text.length === 16 ? `${text}:00` : text
  const date = new Date(`${withSeconds}+08:00`)
  return Number.isNaN(date.getTime()) ? '' : date.toISOString().slice(0, 19)
}

// The first and last instants (ms) of a Singapore date "YYYY-MM-DD".
export function sgtDayStart(day) {
  return day ? new Date(`${day}T00:00:00+08:00`).getTime() : null
}

export function sgtDayEnd(day) {
  return day ? new Date(`${day}T23:59:59.999+08:00`).getTime() : null
}
