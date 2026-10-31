// Hardcoded data — stand-in for what would come from auth + API.
export const roles = {
  organiser: {
    label: 'Event Organiser',
    tabs: ['Dashboard', 'My Events', 'New Request'],
    cards: [
      { title: 'Drafts awaiting submission', sub: '3 requests saved but not yet sent' },
      { title: 'Pending coordinator review', sub: '2 requests under review' },
      { title: 'Upcoming confirmed events', sub: '1 event confirmed for next week' },
      { title: 'Recent comments', sub: 'Coordinator asked about AV needs' }
    ]
  },
  coordinator: {
    label: 'Event Coordinator',
    tabs: ['Dashboard', 'Assigned Events', 'Review Queue', 'Venue Catalogue', 'Venue Calendar', 'Venue Requests', 'Reports'],
    // The Dashboard tab is CoordinatorHome (own events, change requests, re-verification), not cards.
    cards: []
  },
  // Oversees incoming requests: each new request waits, unassigned, until the
  // Lead assigns it to an Event Coordinator. The Lead does not manage events.
  coordinatorlead: {
    label: 'Event Coordinator Lead',
    tabs: ['Dashboard', 'Review Queue', 'Assignments'],
    // The Dashboard tab is LeadDashboard (live counts, waiting requests, workload), not cards.
    cards: []
  },
  venue: {
    label: 'Venue Staff',
    tabs: ['Dashboard', 'Venue Calendar', 'Booking Requests', 'Unavailability', 'Venue Catalogue'],
    // The Dashboard tab is VenueHome (SPM-57: live requests, re-verification, the next few days), not cards.
    cards: []
  },
  techsupport: {
    label: 'Technical Support Staff',
    tabs: ['Dashboard', 'Upcoming Events', 'Venue Catalogue', 'Venue Calendar', 'Equipment Catalogue', 'Reservations', 'My Assignments', 'Maintenance Status'],
    // The Dashboard tab is TechDashboard (live requests, re-verification, shortfalls, supplied events), not cards.
    cards: []
  },
  safety: {
    label: 'Safety Officer',
    tabs: ['Dashboard', 'Safety Reviews'],
    // The Dashboard tab is SafetyDashboard (live counts and decisions), not cards.
    cards: []
  },
  attendee: {
    label: 'Attendee',
    tabs: ['Dashboard', 'Browse Events', 'My Registrations', 'Waiting List'],
    // The Dashboard tab is AttendeeHome (live registrations and open events), not cards.
    cards: []
  }
}
