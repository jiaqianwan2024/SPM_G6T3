import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { bookVenue, planningEvent } from './support/confirmation.js'
import { setEventStatus } from './support/database.js'
import { createPendingRequest, equipmentApi } from './support/equipment.js'
import { assignCoordinator, createSubmittedEvent, eventApi } from './support/event.js'
import { venueRequest } from './support/venue.js'

async function underReviewEvent() {
  const event = await createSubmittedEvent('EO-01', `AUTO-SPM70-${Date.now()}`)
  await assignCoordinator(event.eventId, 'u2')
  return event.eventId
}

test.describe('SPM-70 Reject a submitted request with a reason', () => {
  test('TC-SPM70-AC01 the assigned coordinator can reject Under Review or Changes Requested', async () => {
    const eventId = await underReviewEvent()
    const rejected = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'outside ConnectSphere services',
      explanation: 'Not a venue we support.',
    })
    expect(rejected.status).toBe(200)
    expect(rejected.body.status).toMatch(/rejected/i)
  })

  test('TC-SPM70-AC01 a request with changes requested can also be rejected', async () => {
    const eventId = await underReviewEvent()
    const clarification = await eventApi('POST', `/${eventId}/clarifications`, 'EC-01', {
      message: 'Please confirm expected attendance.',
    })
    expect(clarification.status).toBe(201)
    const rejected = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'insufficient notice',
      explanation: 'Too close to the date.',
    })
    expect(rejected.status).toBe(200)
    expect(rejected.body.status).toMatch(/rejected/i)
  })

  test('TC-SPM70-AC02 a reason is mandatory from the published list, with a free-text explanation', async () => {
    const eventId = await underReviewEvent()
    const missing = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {})
    expect([400, 422]).toContain(missing.status)
    const unlisted = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'dates clash',
      explanation: 'Not on the list.',
    })
    expect([400, 422]).toContain(unlisted.status)
    const noExplanation = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'insufficient notice',
    })
    expect([400, 422]).toContain(noExplanation.status)
    const rejected = await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'no suitable venue available',
      explanation: 'No hall fits the dates.',
    })
    expect(rejected.status).toBe(200)
    expect(rejected.body.decisionReason).toMatch(/venue/)
    expect(rejected.body.decisionNote).toMatch(/hall/)
  })

  test('TC-SPM70-AC03 rejecting moves the event to Rejected, which is terminal', async () => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'insufficient notice',
      explanation: 'Too late',
    })
    const approve = await eventApi('POST', `/${eventId}/approve`, 'EC-01', {})
    expect([400, 409]).toContain(approve.status)
    const stored = await eventApi('GET', `/${eventId}`, 'EC-01')
    expect(stored.body.status).toMatch(/rejected/i)
  })

  test('TC-SPM70-AC04 the organiser is notified and can see the reason and explanation', async ({
    page,
  }) => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'insufficient equipment',
      explanation: 'LED wall unavailable',
    })
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${eventId}`)
    const decision = page.getByTestId('organiser-decision')
    await expect(decision).toContainText(/rejected/i)
    await expect(decision).toContainText('insufficient equipment')
    await expect(decision).toContainText('LED wall unavailable')
  })

  test('TC-SPM70-AC05 rejecting releases venue and equipment holds', async () => {
    // The app books a venue and reserves equipment only once an event is approved for planning, and
    // rejects only while it is under review. So the event gets both in planning and is then put back
    // under review in the database, to check that rejecting releases them.
    const event = await planningEvent('SPM70-release')
    const booking = await bookVenue(event)
    const request = await createPendingRequest({
      eventId: event.eventId,
      equipmentId: 'eq1',
      quantity: 1,
      startsAt: event.period.startsAt,
      endsAt: event.period.endsAt,
      technicalRequirements: 'AUTO-SPM70',
    })
    const reviewed = await equipmentApi('POST', `/equipment/requests/${request.requestId}/review`, 'TS-01', {
      approve: true,
      reviewNote: 'AUTO-SPM70',
    })
    expect(reviewed.status, JSON.stringify(reviewed.body)).toBe(200)
    const reserved = await equipmentApi('POST', `/equipment/requests/${request.requestId}/reserve`, 'TS-01')
    expect(reserved.status, JSON.stringify(reserved.body)).toBe(201)
    setEventStatus(event.eventId, 'under review')

    const rejected = await eventApi('POST', `/${event.eventId}/reject`, 'EC-01', {
      reason: 'outside ConnectSphere services',
      explanation: 'Released',
    })
    expect(rejected.status, JSON.stringify(rejected.body)).toBe(200)
    const viewed = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect(viewed.body.status).toBe('cancelled')
    const reservations = await equipmentApi('GET', `/equipment/reservations?eventId=${event.eventId}`, 'TS-01')
    expect(reservations.body.map((row) => row.status)).toEqual(['released'])
  })

  test('TC-SPM70-AC06 the rejected event stays in organiser history and the activity log', async () => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'insufficient notice',
      explanation: 'Keep history',
    })
    const list = await eventApi('GET', '', 'EO-01')
    expect((list.body || []).map((row) => row.eventId)).toContain(eventId)
    const log = await eventApi('GET', `/${eventId}/activity-log`, 'EO-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/reject/)
  })

  test('TC-SPM70-AC07 the organiser can create a fresh request after a rejection', async () => {
    const eventId = await underReviewEvent()
    await eventApi('POST', `/${eventId}/reject`, 'EC-01', {
      reason: 'outside ConnectSphere services',
      explanation: 'Try again',
    })
    const fresh = await createSubmittedEvent('EO-01', 'AUTO-SPM70-fresh')
    expect(fresh.eventId).not.toBe(eventId)
    expect(fresh.status).toMatch(/submitted/i)
  })
})
