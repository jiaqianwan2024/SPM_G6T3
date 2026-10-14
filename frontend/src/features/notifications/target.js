// Where a notification takes the reader (SPM-94 AC3). Notifications published
// by a service carry a `link`; older ones only name their event.
export function notificationTarget(item) {
  if (item.link && item.link.startsWith('/app/')) return item.link
  if (item.eventId) return `/app/events/${item.eventId}`
  return null
}
