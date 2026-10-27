// Hardcoded data — stand-in for what would come from auth + API.
export const roles = {
  organiser: {
    label: 'Event Organiser',
    tabs: ['Dashboard', 'My Events', 'New Request', 'Drafts'],
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
    cards: [
      { title: 'Review queue', sub: '4 requests need clarification' },
      { title: 'Venue requests in progress', sub: '2 awaiting Venue Staff decision' },
      { title: 'Outstanding arrangements', sub: '1 event missing equipment sign-off' },
      { title: 'Recently confirmed', sub: 'Q3 Partner Summit confirmed' }
    ]
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
    cards: [
      { title: 'Pending booking requests', sub: '3 requests to approve or reject' },
      { title: 'Blocked for maintenance', sub: 'Hall B closed until Friday' },
      { title: 'Turnaround conflicts', sub: 'Tight changeover flagged for Rm 204' },
      { title: "This week's setups", sub: '5 events need setup confirmation' }
    ]
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
