import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { confirm, events, readyToConfirm } from './support/confirmation.js'
import { moveIntoPast } from './support/database.js'
import { guestRegistration, registrationApi } from './support/registration.js'
import { venueRequest } from './support/venue.js'

// SPM-73: the suite makes its own confirmed events (Theatre, 50 people, Marina Hall A booked, assigned to
// EC-01) instead of reading seeded e1, which other specs change. A finished event cannot be made through
// the app, so `ended` and `done` are moved into the past in the database after they are confirmed
// (e2e/support/database.js). `done` is also completed here, so the tests after AC02 do not depend on it.

const DAY = 24 * 60 * 60 * 1000

let ahead // confirmed, still to take place
let ended // confirmed, ended two days ago
let done // confirmed, ended two days ago, then completed; ATT-01 registered while it was open
let registration

async function confirmedEvent(label, extras) {
  const event = await readyToConfirm(label, extras)
  const confirmed = await confirm(event)
  expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)
  return event
}

test.describe('SPM-73 Mark an event completed', () => {
  test.beforeAll(async () => {
    // Three events, each planned, booked, reviewed for safety and confirmed: more than one test's time.
    test.setTimeout(240_000)
    const now = Date.now()
    ahead = await confirmedEvent('SPM73-ahead')
    ended = await confirmedEvent('SPM73-ended')
    done = await confirmedEvent('SPM73-done', {
      registrationEnabled: true,
      registrationOpensAt: new Date(now - DAY).toISOString(),
      registrationClosesAt: new Date(now + 60 * DAY).toISOString(),
    })
    const registered = await registrationApi('POST', '/registrations', 'ATT-01', guestRegistration(done.eventId, 'SPM73'))
    expect(registered.status, JSON.stringify(registered.body)).toBe(201)
    registration = registered.body
    moveIntoPast(ended.eventId)
    moveIntoPast(done.eventId)
    const completed = await events('POST', `/${done.eventId}/complete`, 'EC-01')
    expect(completed.status, JSON.stringify(completed.body)).toBe(200)
  })

  test('TC-SPM73-AC01 a confirmed event can be completed only after its end time has passed', async () => {
    const early = await events('POST', `/${ahead.eventId}/complete`, 'EC-01')
    expect(early.status).toBe(409)
    expect(early.body.detail).toBe('This event cannot be marked completed until its end time has passed')
    expect((await events('GET', `/${ahead.eventId}`, 'EC-01')).body.status).toBe('confirmed')
    // Only the assigned coordinator, even once the end has passed.
    expect((await events('POST', `/${ended.eventId}/complete`, 'EC-02')).status).toBe(403)
  })

  test('TC-SPM73-AC02 completing moves the event to Completed and records who and when', async () => {
    const before = Date.now()
    const result = await events('POST', `/${ended.eventId}/complete`, 'EC-01')
    expect(result.status, JSON.stringify(result.body)).toBe(200)
    expect(result.body.status).toBe('completed')

    const log = await events('GET', `/${ended.eventId}/activity-log`, 'EC-01')
    const entry = log.body.find((row) => row.kind === 'status' && row.toStatus === 'completed')
    expect(entry.fromStatus).toBe('confirmed')
    expect(entry.changedBy).toBe('u2')
    // Server times are UTC without a zone marker.
    expect(new Date(`${entry.createdAt}Z`).getTime()).toBeGreaterThanOrEqual(before - 60_000)
  })

  test('TC-SPM73-AC03 a completed event no longer counts against future availability', async () => {
    const [booking] = (await venueRequest('GET', `/venues/bookings?eventId=${done.eventId}`, 'VS-01')).body
    expect(new Date(`${booking.teardownEndsAt}Z`).getTime()).toBeLessThan(Date.now())
    // Its venue is free for a slot to come.
    const startsAt = new Date(Date.now() + 3 * DAY)
    startsAt.setUTCHours(2, 0, 0, 0)
    const endsAt = new Date(startsAt.getTime() + 2 * 60 * 60 * 1000)
    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${startsAt.toISOString().slice(0, 19)}&endsAt=${endsAt.toISOString().slice(0, 19)}`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    expect(search.body.map((venue) => venue.venueId)).toContain(booking.venueId)
  })

  test('TC-SPM73-AC04 a completed event stays readable with its activity log and clarifications intact', async () => {
    const event = await events('GET', `/${done.eventId}`, 'EO-01')
    expect(event.status).toBe(200)
    expect(event.body.status).toBe('completed')
    const log = await events('GET', `/${done.eventId}/activity-log`, 'EC-01')
    expect(log.status).toBe(200)
    expect(log.body.some((row) => row.toStatus === 'completed')).toBe(true)
    expect((await events('GET', `/${done.eventId}/clarifications`, 'EC-01')).status).toBe(200)
  })

  test('TC-SPM73-AC05 completed events are excluded from active queues by default and can be filtered back', async ({
    page,
  }) => {
    await login(page, account('ECL-01'))
    await page.locator('.nav-item').getByText('Review Queue', { exact: true }).click()
    await expect(page.getByTestId('queue-include-completed')).toBeVisible()
    await expect(page.getByTestId(`review-queue-${done.eventId}`)).toHaveCount(0)
    await page.getByTestId('queue-include-completed').check()
    await expect(page.getByTestId(`review-queue-${done.eventId}`)).toBeVisible()
  })

  test('TC-SPM73-EXTRA01 the queue API leaves completed events out unless includeCompleted is set', async () => {
    const ids = async (path) => (await events('GET', path, 'ECL-01')).body.map((row) => row.eventId)
    expect(await ids('/queue')).not.toContain(done.eventId)
    expect(await ids('/queue?includeCompleted=true')).toContain(done.eventId)
  })

  test('TC-SPM73-AC06 attendees cannot register for or withdraw from a completed event', async () => {
    const withdraw = await registrationApi('POST', `/registrations/${registration.attendeeRegistrationId}/withdraw`, 'ATT-01', {})
    expect(withdraw.status).toBe(409)
    expect(withdraw.body.detail).toContain('completed')
    const register = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration(done.eventId, 'SPM73b'))
    expect(register.status).toBe(409)
  })
})
