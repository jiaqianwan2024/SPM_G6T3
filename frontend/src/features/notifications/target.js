// Where a notification takes the reader (SPM-94 AC3). Notifications published
// by a service carry a `link`; older ones only name their event. An attendee
// cannot open the staff event page (SPM-127), so an event link takes them to
// that event's public page instead.
export function notificationTarget(item, role = '') {
  const link = item.link && item.link.startsWith('/app/') ? item.link : item.eventId ? `/app/events/${item.eventId}` : null
  const eventPage = link && link.match(/^\/app\/events\/([^/?#]+)$/)
  if (role === 'attendee' && eventPage) return `/app/browse/${eventPage[1]}`
  return link
}
