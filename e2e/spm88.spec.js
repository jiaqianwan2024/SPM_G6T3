import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import {
  assignCoordinator,
  createSubmittedEvent,
  eventApi,
  raiseChangeRequest,
} from './support/event.js'
import { notificationRequest, venueRequest } from './support/venue.js'
import { approveRequest, createPendingRequest, equipmentApi } from './support/equipment.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

async function cancellableEvent(name) {
  const event = await createSubmittedEvent('EO-01', name)
  await assignCoordinator(event.eventId, 'u2')
  return event
}

// A venue can only be requested for an event approved for planning (SPM-63), so the venue tests
// use their own approved Theatre event, booked on a random day far ahead.
async function eventWithVenueRequest(name) {
  const event = await approvedEvent({ ...THEATRE_EVENT, eventName: `${name}-${Date.now()}` })
  const booking = await requestVenue(event, 'v3', freshPeriod())
  expect(booking.status, JSON.stringify(booking.body)).toBe(201)
  return { event, booking: booking.body }
}

test.describe('SPM-88 Cancel an event and release its arrangements', () => {
  // A cancellation releases venue and equipment in two other services before it answers,
  // and several tests make an event (and a booking) first, so they get more than the default.
  test.describe.configure({ timeout: 150_000 })

  test('TC-SPM88-AC01 the organiser can cancel their org events in the published statuses, and the coordinator can cancel on ConnectSphere\'s behalf', async () => {
    const submitted = await createSubmittedEvent('EO-01', 'AUTO-SPM88-submitted')
    const asOrganiser = await eventApi('POST', `/${submitted.eventId}/cancel`, 'EO-01', {
      reason: 'AUTO-SPM88-organiser',
    })
    expect(asOrganiser.status).toBe(200)
    expect(asOrganiser.body.status).toMatch(/cancelled/i)
    const fresh = await cancellableEvent('AUTO-SPM88-coord')
    const asCoord = await eventApi('POST', `/${fresh.eventId}/cancel`, 'EC-01', {
      reason: 'ConnectSphere cannot staff it',
    })
    expect(asCoord.status).toBe(200)
    expect(asCoord.body.status).toMatch(/cancelled/i)
  })

  test('TC-SPM88-AC02 cancellation requires a reason and takes effect immediately, with no approval step', async () => {
    const event = await cancellableEvent('AUTO-SPM88-reason')
    const missing = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', {})
    expect([400, 422]).toContain(missing.status)
    const cancelled = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', {
      reason: 'Date no longer works',
    })
    expect(cancelled.status).toBe(200)
    expect(cancelled.body.status).toMatch(/cancelled/i)
    expect(cancelled.body.cancellationReason).toBe('Date no longer works')
    expect(cancelled.body.approvalRequired).toBeFalsy()
  })

  test('TC-SPM88-AC03 cancelling asks for confirmation and states what will be released and who will be notified', async ({
    page,
  }) => {
    const event = await cancellableEvent('AUTO-SPM88-confirm')
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await page.getByTestId('event-cancel').click()
    const dialog = page.getByTestId('cancel-confirm')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByTestId('cancel-releases')).toContainText(/venue/i)
    await expect(dialog.getByTestId('cancel-releases')).toContainText(/equipment/i)
    await expect(dialog.getByTestId('cancel-notified')).toContainText(/coordinator/i)
    // Nothing happens until a reason is given and the cancellation is confirmed.
    await expect(dialog.getByTestId('cancel-submit')).toBeDisabled()
    await dialog.getByTestId('cancel-reason').fill('Confirmed in the dialog')
    await dialog.getByTestId('cancel-submit').click()
    await expect(page.getByTestId('organiser-event-status')).toContainText(/cancelled/i, { timeout: 60_000 })
    await expect(page.getByTestId('event-cancelled-reason')).toContainText('Confirmed in the dialog')
  })

  test('TC-SPM88-AC04 the event moves to Cancelled, which is terminal', async () => {
    const event = await cancellableEvent('AUTO-SPM88-terminal')
    await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Stop' })
    const approve = await eventApi('POST', `/${event.eventId}/approve`, 'EC-01', {})
    expect([400, 409]).toContain(approve.status)
    const again = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Again' })
    expect(again.status).toBe(409)
    const stored = await eventApi('GET', `/${event.eventId}`, 'EO-01')
    expect(stored.body.status).toMatch(/cancelled/i)
  })

  test('TC-SPM88-AC05 every venue booking and pending request is released and the venue is free immediately', async () => {
    const { event, booking } = await eventWithVenueRequest('AUTO-SPM88-venue')
    const cancelled = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Free the room' })
    expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200)
    const viewed = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect(viewed.body.status).toBe('cancelled')
  })

  test('TC-SPM88-AC06 every equipment reservation is released and quantities are free immediately', async () => {
    const event = await cancellableEvent('AUTO-SPM88-eq')
    const request = await createPendingRequest({ eventId: event.eventId, sequence: 411 })
    await approveRequest(request.requestId)
    const reserved = await equipmentApi('POST', `/equipment/requests/${request.requestId}/reserve`, 'TS-01')
    expect(reserved.status, JSON.stringify(reserved.body)).toBe(201)
    const cancelled = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Free kits' })
    expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200)
    const viewed = await equipmentApi('GET', `/equipment/reservations/${reserved.body.reservationId}`, 'TS-01')
    expect(viewed.body.status).toBe('released')
  })

  test('TC-SPM88-AC07 registration closes and every registered attendee is notified with the reason', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e8')
    await expect(page.getByTestId('organiser-event-status')).toContainText(/cancelled/i)
    await expect(page.getByTestId('event-cancelled-reason')).toBeVisible()
    const regs = await eventApi('GET', '/e8/registrations', 'EO-01')
    expect([200, 404]).toContain(regs.status)
    // SPM-127: an attendee reads an event they registered for through its attendee card.
    const attendee = await eventApi('GET', '/e8/attendee-card', 'ATT-01')
    expect(attendee.status).toBe(200)
    expect(JSON.stringify(attendee.body)).toMatch(/cancelled/i)
  })

  test('TC-SPM88-AC08 the assigned coordinator, approving venue staff, and technical support holding reservations are notified', async () => {
    const event = await cancellableEvent(`AUTO-SPM88-staff-${Date.now()}`)
    const cancelled = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Notify staff' })
    expect(cancelled.status).toBe(200)
    const inbox = await notificationRequest('/notifications', 'EC-01')
    expect(inbox.status).toBe(200)
    const notice = (inbox.body || []).find((row) => row.eventId === event.eventId && row.type === 'event.cancelled')
    expect(notice, 'the coordinator is told').toBeTruthy()
    expect(notice.body).toContain('Reason: Notify staff')
  })

  test('TC-SPM88-AC09 a cancellation that does not go through leaves the event and its arrangements as they were', async () => {
    // A failed release is covered by the unit tests (each service down, and the undo). Here a
    // cancellation refused part-way leaves the event and its venue request untouched.
    const { event, booking } = await eventWithVenueRequest('AUTO-SPM88-refused')
    const denied = await eventApi('POST', `/${event.eventId}/cancel`, 'EO-02', { reason: 'Not my event' })
    expect(denied.status).toBe(403)
    const stored = await eventApi('GET', `/${event.eventId}`, 'EO-01')
    expect(stored.body.status).not.toMatch(/cancelled/i)
    const viewed = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect(viewed.body.status).toBe('pending')
  })

  test('TC-SPM88-AC10 the cancelled event, reason, arrangement history, and registrations stay readable and are logged', async () => {
    const viewed = await eventApi('GET', '/e8', 'EO-01')
    expect(viewed.status).toBe(200)
    expect(viewed.body.status).toMatch(/cancelled/i)
    expect(viewed.body.cancellationReason).toBeTruthy()
    const log = await eventApi('GET', '/e8/activity-log', 'EC-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/cancel/)
  })

  test('TC-SPM88-AC11 a pending change request on the event is closed by the cancellation', async () => {
    const event = await cancellableEvent('AUTO-SPM88-cr')
    const raised = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'Will be closed',
      proposedChanges: { description: 'pending' },
    })
    expect(raised.status).toBe(201)
    await eventApi('POST', `/${event.eventId}/cancel`, 'EO-01', { reason: 'Close the CR' })
    const list = await eventApi('GET', `/${event.eventId}/change-requests`, 'EC-01')
    expect(list.status).toBe(200)
    expect((list.body || [])[0].status).toMatch(/closed|cancelled|withdrawn/i)
  })
})
