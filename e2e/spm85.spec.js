import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import {
  assignCoordinator,
  createSubmittedEvent,
  eventApi,
  raiseChangeRequest,
} from './support/event.js'

async function pendingChange(name, changes) {
  const event = await createSubmittedEvent('EO-01', name)
  await assignCoordinator(event.eventId, 'u2')
  const raised = await raiseChangeRequest(event.eventId, 'EO-01', {
    reason: 'AUTO-SPM85',
    proposedChanges: changes,
  })
  expect(raised.status).toBe(201)
  return { event, change: raised.body }
}

test.describe('SPM-85 Review and decide a change request', () => {
  test('TC-SPM85-AC01 the assigned coordinator sees current and proposed values and the reason', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e1/change-requests/cr-new')
    const panel = page.getByTestId('change-request-review')
    await expect(panel).toBeVisible()
    await expect(panel).toContainText(/equipment|handheld|mics/i)
    await expect(panel.getByTestId('change-current')).toBeVisible()
    await expect(panel.getByTestId('change-proposed')).toBeVisible()
    await expect(panel).toContainText(/New AV change|reason/i)
    await expect(page.getByTestId('change-request-impact')).toBeVisible()
  })

  test('TC-SPM85-AC02 before deciding, the coordinator sees an impact assessment of venue, equipment, and registration', async () => {
    const impact = await eventApi('GET', '/e1/change-requests/cr-new/impact', 'EC-01')
    expect(impact.status).toBe(200)
    expect(Array.isArray(impact.body.venueBookings)).toBe(true)
    expect(Array.isArray(impact.body.equipmentReservations)).toBe(true)
    expect(Array.isArray(impact.body.registrations)).toBe(true)
    // cr-new only changes the equipment notes, so the equipment part is read and nothing is left unchecked.
    expect(impact.body.unchecked).toEqual([])
  })

  test('TC-SPM85-AC03 a date, time, or layout change re-runs venue suitability and shows the verdict', async () => {
    const { event, change } = await pendingChange('AUTO-SPM85-suit', {
      proposedStartAt: new Date(Date.now() + 16 * 86400000).toISOString(),
      layoutPreference: 'Banquet',
    })
    const impact = await eventApi(
      'GET',
      `/${event.eventId}/change-requests/${change.changeRequestId}/impact`,
      'EC-01',
    )
    expect(impact.status).toBe(200)
    // Re-run for every booked venue: a list (empty when nothing is booked yet), never null.
    expect(Array.isArray(impact.body.venueSuitability)).toBe(true)
    for (const row of impact.body.venueSuitability) {
      expect(['suitable', 'suitable with warnings', 'not suitable']).toContain(row.verdict)
    }
  })

  test('TC-SPM85-AC04 raising attendance above booked layout capacity names both figures', async () => {
    const { event, change } = await pendingChange('AUTO-SPM85-cap', {
      expectedAttendance: 500,
    })
    const impact = await eventApi(
      'GET',
      `/${event.eventId}/change-requests/${change.changeRequestId}/impact`,
      'EC-01',
    )
    expect(impact.status).toBe(200)
    expect(Array.isArray(impact.body.capacity)).toBe(true)
    for (const row of impact.body.capacity) {
      expect(row.expectedAttendance).toBe(500)
      expect(row.overCapacity).toBe(500 > row.capacity)
    }
  })

  test('TC-SPM85-AC05 raising an equipment quantity reports whether the extra units are available', async () => {
    const { event, change } = await pendingChange('AUTO-SPM85-eq', {
      equipmentRequirements: 'Projector PX-200 x 20',
      equipmentLines: [{ equipmentId: 'eq1', quantity: 20 }],
    })
    const impact = await eventApi(
      'GET',
      `/${event.eventId}/change-requests/${change.changeRequestId}/impact`,
      'EC-01',
    )
    expect(impact.status).toBe(200)
    const [line] = impact.body.equipmentAvailability
    expect(line).toMatchObject({ equipmentId: 'eq1', currentQuantity: 0, proposedQuantity: 20, extraQuantity: 20 })
    expect(line.available).toBe(line.shortfall === 0)
    expect(line.shortfall).toBe(Math.max(20 - line.freeQuantity - line.heldQuantity, 0))
  })

  test('TC-SPM85-AC06 accepting applies the proposed values, records the decision, and notifies the organiser', async ({
    page,
  }) => {
    const { event, change } = await pendingChange('AUTO-SPM85-accept', {
      description: 'Accepted description',
    })
    const accepted = await eventApi(
      'POST',
      `/${event.eventId}/change-requests/${change.changeRequestId}/accept`,
      'EC-01',
    )
    expect(accepted.status).toBe(200)
    const stored = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body.description).toMatch(/Accepted description/)
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('change-request-outcome')).toContainText(/accepted|applied/i)
  })

  test('TC-SPM85-AC07 declining requires a reason, leaves the event untouched, and notifies the organiser', async ({
    page,
  }) => {
    const { event, change } = await pendingChange('AUTO-SPM85-decline', {
      eventName: 'Should not apply',
    })
    const missing = await eventApi(
      'POST',
      `/${event.eventId}/change-requests/${change.changeRequestId}/decline`,
      'EC-01',
      {},
    )
    expect([400, 422]).toContain(missing.status)
    const declined = await eventApi(
      'POST',
      `/${event.eventId}/change-requests/${change.changeRequestId}/decline`,
      'EC-01',
      { reason: 'Venue cannot move that week' },
    )
    expect(declined.status).toBe(200)
    const stored = await eventApi('GET', `/${event.eventId}`, 'EO-01')
    expect(stored.body.eventName).not.toBe('Should not apply')
    await login(page, account('EO-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await expect(page.getByTestId('change-request-outcome')).toContainText(/declin|Venue cannot move/i)
  })

  test('TC-SPM85-AC08 the coordinator accepts part of a request by declining with a reason asking for a narrower one', async () => {
    const { event, change } = await pendingChange('AUTO-SPM85-narrow', {
      eventName: 'New name',
      expectedAttendance: 200,
    })
    const declined = await eventApi(
      'POST',
      `/${event.eventId}/change-requests/${change.changeRequestId}/decline`,
      'EC-01',
      { reason: 'Please raise attendance only; name stays.', askNarrower: true },
    )
    expect(declined.status).toBe(200)
    expect(declined.body).toMatchObject({ status: 'declined', narrowerRequested: true })
    const stored = await eventApi('GET', `/${event.eventId}`, 'EC-01')
    expect(stored.body.eventName).not.toBe('New name')
    expect(stored.body.expectedAttendance).not.toBe(200)
    const narrower = await raiseChangeRequest(event.eventId, 'EO-01', {
      reason: 'AUTO-SPM85 narrower',
      proposedChanges: { expectedAttendance: 200 },
    })
    expect(narrower.status).toBe(201)
  })

  test('TC-SPM85-AC09 the decision, fields, previous and new values, decider, and time are in the activity log', async () => {
    const { event, change } = await pendingChange('AUTO-SPM85-log', {
      purpose: 'Logged purpose',
    })
    await eventApi(
      'POST',
      `/${event.eventId}/change-requests/${change.changeRequestId}/accept`,
      'EC-01',
    )
    const log = await eventApi('GET', `/${event.eventId}/activity-log`, 'EC-01')
    expect(log.status).toBe(200)
    const decision = log.body.find((entry) => entry.kind === 'change_request')
    expect(decision).toMatchObject({ decision: 'accepted', changedBy: 'u2' })
    expect(decision.createdAt).toBeTruthy()
    expect(decision.changes).toEqual([
      { field: 'purpose', oldValue: 'Acceptance test event.', newValue: 'Logged purpose' },
    ])
  })
})
