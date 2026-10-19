import { test, expect } from '@playwright/test'
import { serviceUrls } from './support/api-data.js'
import { authedApi } from './support/auth.js'
import { assignCoordinator, eventApi } from './support/event.js'
import { createEquipment, equipmentApi } from './support/equipment.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import { createSuiteVenue, period, retireSuiteVenue } from './support/venue-suite.js'

// SPM-45: each role may only do what its job needs. The suite makes its own venue
// and equipment item (retired or left unused afterwards) and its own events, each
// on its own fixed day, so it never depends on seeded bookings or stock that an
// earlier run used up. Since SPM-117 (Week 7 change 5) only the Event Coordinator
// Lead assigns coordinators, so AC3's "coordinators can assign" now reads: the Lead
// assigns, and a coordinator who tries is refused.

let hall
let projector

async function pendingBooking(day) {
  const event = await approvedEvent(THEATRE_EVENT)
  const sent = await requestVenue(event, hall.venueId, period(day))
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  return { event, booking: sent.body }
}

function equipmentRequest(event, accountId, day) {
  const when = period(day)
  return equipmentApi('POST', '/equipment/requests', accountId, {
    eventId: event.eventId,
    equipmentId: projector.equipmentId,
    quantity: 1,
    technicalRequirements: 'AUTO-SPM45 HDMI to the stage',
    startsAt: when.startsAt,
    endsAt: when.endsAt,
  })
}

function decide(booking, decision, accountId, reason = 'AUTO-SPM45') {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/${decision}`, accountId, { reason })
}

function assign(event, accountId) {
  return eventApi('POST', `/${event.eventId}/assign-coordinator`, accountId, { coordinatorId: 'u2' })
}

test.describe('SPM-45 Role-Based Feature Access Control (API)', () => {
  test.beforeAll(async () => {
    hall = await createSuiteVenue('SPM45 Hall', { layouts: [{ name: 'Theatre', capacity: 300 }] })
    projector = await createEquipment(`AUTO-SPM45 Projector ${Date.now()}`)
  })

  test.afterAll(async () => {
    await retireSuiteVenue(hall)
  })

  test('TC-SPM45-AC01 Venue Staff approve and reject bookings, but cannot request equipment or assign coordinators', async () => {
    const toApprove = await pendingBooking(1)
    const toReject = await pendingBooking(2)

    const approved = await decide(toApprove.booking, 'approve', 'VS-01')
    const rejected = await decide(toReject.booking, 'reject', 'VS-01', 'AUTO-SPM45 turnaround conflict')
    const equipment = await equipmentRequest(toApprove.event, 'VS-01', 1)
    const assignment = await assign(toApprove.event, 'VS-01')

    expect([approved.status, approved.body.status]).toEqual([200, 'approved'])
    expect([rejected.status, rejected.body.status, rejected.body.decisionReason]).toEqual([
      200,
      'rejected',
      'AUTO-SPM45 turnaround conflict',
    ])
    expect(equipment.status).toBe(403)
    expect(assignment.status).toBe(403)
  })

  test('TC-SPM45-AC02 Technical Support review and reserve equipment, but cannot decide venue bookings', async () => {
    const { event, booking } = await pendingBooking(3)
    const created = await equipmentRequest(event, 'EC-01', 3)
    expect([created.status, created.body.status]).toEqual([201, 'pending'])

    const reviewed = await equipmentApi('POST', `/equipment/requests/${created.body.requestId}/review`, 'TS-01', {
      approve: true,
      reviewNote: 'AUTO-SPM45 stock confirmed',
    })
    const reserved = await equipmentApi('POST', `/equipment/requests/${created.body.requestId}/reserve`, 'TS-01')
    expect([reviewed.status, reviewed.body.status]).toEqual([200, 'approved'])
    expect([reserved.status, reserved.body.status]).toEqual([201, 'active'])

    for (const decision of ['approve', 'reject']) {
      expect((await decide(booking, decision, 'TS-01')).status, decision).toBe(403)
    }
    const stillPending = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect(stillPending.body.status).toBe('pending')
  })

  test('TC-SPM45-AC03 Event Coordinators submit venue and equipment requests but cannot approve their own bookings or assign', async () => {
    const { event, booking } = await pendingBooking(4)
    expect(booking.status).toBe('pending')
    const equipment = await equipmentRequest(event, 'EC-01', 4)
    expect([equipment.status, equipment.body.status]).toEqual([201, 'pending'])

    for (const decision of ['approve', 'reject']) {
      expect((await decide(booking, decision, 'EC-01')).status, decision).toBe(403)
    }
    expect((await assign(event, 'EC-01')).status).toBe(403)
    // The Lead assigns instead (SPM-117): here, moving the event to EC-02 (u6).
    expect((await assignCoordinator(event.eventId, 'u6')).coordinatorId).toBe('u6')

    const byVenueStaff = await decide(booking, 'approve', 'VS-01')
    expect([byVenueStaff.status, byVenueStaff.body.reviewedBy]).toEqual([200, 'u3'])
  })

  test('TC-SPM45-AC04 an action outside the caller\'s role is refused with 403', async () => {
    const { event, booking } = await pendingBooking(5)
    const when = period(5)
    const attempts = {
      'Venue Staff cannot assign coordinators': () => assign(event, 'VS-01'),
      'Technical Support cannot send venue booking requests': () =>
        venueRequest('POST', '/venues/bookings', 'TS-01', { eventId: event.eventId, venueId: hall.venueId, ...when }),
      'An Event Coordinator cannot approve venue bookings': () => decide(booking, 'approve', 'EC-01'),
      'An Event Organiser cannot request equipment': () => equipmentRequest(event, 'EO-01', 5),
      'An Attendee cannot reject venue bookings': () => decide(booking, 'reject', 'ATT-01'),
      'An Attendee cannot open the coordinator review queue': () =>
        authedApi('GET', `${serviceUrls.event}/events/queue`, 'ATT-01'),
    }

    for (const [name, attempt] of Object.entries(attempts)) {
      const response = await attempt()
      expect(response.status, name).toBe(403)
      expect(response.body.detail, name).toMatch(/permission|only|not allowed/i)
    }
    const unchanged = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect(unchanged.body.status).toBe('pending')
  })
})
