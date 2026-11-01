import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { guestRegistration, notificationApi, openEvent, registrationApi, releaseEvents } from './support/registration.js'

const DAY = 86400000

// Seeded e1 has a single place left, so tests that register create a confirmed event of their own
// rather than take each other's place. They are withdrawn from and cancelled once the spec is done.
const created = []
async function confirmedEvent(label, options) {
  const event = await openEvent(label, options)
  created.push(event.eventId)
  return event
}

async function remainingPlaces(eventId, accountId) {
  const summary = await registrationApi('GET', `/registrations?eventId=${eventId}`, accountId)
  expect(summary.status, JSON.stringify(summary.body)).toBe(200)
  return summary.body.remainingPlaces ?? summary.body.placesRemaining
}

test.describe('SPM-11 Register for an event', () => {
  test.afterAll(async () => releaseEvents(created))

  test('TC-SPM11-AC01 registration succeeds only for a confirmed, enabled, in-period event with a place remaining', async () => {
    const event = await confirmedEvent('SPM11-open')
    const ok = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration(event.eventId, 'SPM11-OK'))
    expect(ok.status, JSON.stringify(ok.body)).toBe(201)
    expect(ok.body.eventId).toBe(event.eventId)
    // e3 is in planning and e6 is submitted: neither is confirmed.
    const planning = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e3', 'SPM11-E3'))
    expect([400, 409]).toContain(planning.status)
    const submitted = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e6', 'SPM11-E6'))
    expect([400, 404, 409]).toContain(submitted.status)
    // e7 is confirmed but does not take registrations.
    const disabled = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e7', 'SPM11-E7'))
    expect(disabled.status).toBe(409)
    expect(JSON.stringify(disabled.body)).toMatch(/not been enabled/i)
  })

  test('TC-SPM11-AC02 the attendee registers only themselves, and a blank mandatory field blocks submit with inline validation', async ({
    page,
  }) => {
    const event = await confirmedEvent('SPM11-blank')
    await login(page, account('ATT-02'))
    await page.goto(`/app/browse/${event.eventId}`)
    await page.getByTestId('event-register').click()
    // The name starts as the account's; the email is the account's and cannot be changed.
    await expect(page.getByTestId('register-email')).toHaveValue('attendee2@connectsphere.com')
    await expect(page.getByTestId('register-email')).toHaveAttribute('readonly', '')
    await page.getByTestId('register-name').fill('')
    await page.getByTestId('register-submit').click()
    await expect(page.getByTestId('register-name-error')).toBeVisible()
    const empty = await registrationApi('POST', '/registrations', 'ATT-02', {
      eventId: event.eventId,
      name: '',
      email: '',
    })
    expect(empty.status).toBe(409)
    expect(JSON.stringify(empty.body)).toMatch(/Name and email are required/)
    expect(await remainingPlaces(event.eventId, 'ATT-01')).toBe(5)
  })

  test('TC-SPM11-AC03 a registration reduces remaining places by one, visible immediately to other attendees', async () => {
    const event = await confirmedEvent('SPM11-count')
    const before = await remainingPlaces(event.eventId, 'ATT-01')
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration(event.eventId, 'SPM11-DEC'),
    )
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    expect(await remainingPlaces(event.eventId, 'ATT-01')).toBe(before - 1)
  })

  test('TC-SPM11-AC04 a second registration for the same attendee is refused and the existing one is shown', async ({
    page,
  }) => {
    // ATT-01 holds r-att-e1 from the seed.
    const again = await registrationApi('POST', '/registrations', 'ATT-01', {
      eventId: 'e1',
      name: 'Amy Wong',
      email: 'attendee@connectsphere.com',
    })
    expect(again.status).toBe(409)
    expect(JSON.stringify(again.body)).toMatch(/already registered/i)
    await login(page, account('ATT-01'))
    await page.goto('/app/browse/e1')
    await expect(page.getByTestId('existing-registration')).toBeVisible()
    await expect(page.getByTestId('existing-registration')).toContainText(/registered|Amy Wong/i)
  })

  test('TC-SPM11-AC05 registration is refused when the event is full', async ({ page }) => {
    // e2 is seeded at capacity (r2, r3 and r-att-e2 against 2 places).
    const denied = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e2', 'SPM11-FULL'))
    expect([400, 409]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/full|capacity/i)
    await login(page, account('ATT-02'))
    await page.goto('/app/browse/e2')
    await expect(page.getByTestId('event-full')).toBeVisible()
  })

  test('TC-SPM11-AC06 registration outside the period is refused with the period stated', async () => {
    // e4's period opens in two days.
    const early = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e4', 'SPM11-EARLY'))
    expect(early.status).toBe(409)
    expect(JSON.stringify(early.body)).toMatch(/not opened yet.*registration period is .* to .* SGT/i)
    const closed = await confirmedEvent('SPM11-closed', { opensAt: Date.now() - 3 * DAY, closesAt: Date.now() - DAY })
    const late = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration(closed.eventId, 'SPM11-LATE'))
    expect(late.status).toBe(409)
    expect(JSON.stringify(late.body)).toMatch(/closed.*registration period was .* to .* SGT/i)
  })

  test('TC-SPM11-AC07 two attendees submitting for the last place: exactly one succeeds', async () => {
    const event = await confirmedEvent('SPM11-race', { capacity: 1 })
    const [first, second] = await Promise.all([
      registrationApi('POST', '/registrations', 'ATT-02', guestRegistration(event.eventId, 'SPM11-RACE-A')),
      registrationApi('POST', '/registrations', 'ATT-01', guestRegistration(event.eventId, 'SPM11-RACE-B')),
    ])
    const statuses = [first.status, second.status].sort()
    expect(statuses[0]).toBe(201)
    expect([409, 400]).toContain(statuses[1])
    const refused = first.status === 201 ? second : first
    expect(JSON.stringify(refused.body)).toMatch(/full|capacity/i)
  })

  test('TC-SPM11-AC08 every condition is enforced on the server when the endpoint is called directly', async () => {
    const cases = [
      ['e3', /not been confirmed/i],
      ['e7', /not been enabled/i],
      ['e4', /not opened yet/i],
      ['e2', /full|capacity/i],
    ]
    for (const [eventId, reason] of cases) {
      const refused = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration(eventId, 'SPM11-API'))
      expect(refused.status, `${eventId}: ${JSON.stringify(refused.body)}`).toBe(409)
      expect(JSON.stringify(refused.body)).toMatch(reason)
    }
    // An attendee cannot register someone else: only their own account's email is accepted.
    const event = await confirmedEvent('SPM11-someone-else')
    const forSomeoneElse = await registrationApi('POST', '/registrations', 'ATT-02', {
      eventId: event.eventId,
      name: 'Someone Else',
      email: 'someone.else@example.com',
    })
    expect(forSomeoneElse.status).toBe(403)
    expect(JSON.stringify(forSomeoneElse.body)).toMatch(/only register yourself/i)
    expect(await remainingPlaces(event.eventId, 'ATT-01')).toBe(5)
  })

  test('TC-SPM11-AC09 reaching capacity notifies the organiser and the assigned coordinator', async () => {
    const event = await confirmedEvent('SPM11-full', { capacity: 1 })
    const taken = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration(event.eventId, 'SPM11-FULL-LAST'))
    expect(taken.status, JSON.stringify(taken.body)).toBe(201)
    for (const accountId of ['EO-01', 'EC-01']) {
      await expect
        .poll(async () => {
          const inbox = await notificationApi('GET', '/notifications?pageSize=50', accountId)
          return (inbox.body || []).some((row) => row.eventId === event.eventId && row.type === 'registration.full')
        }, { message: `${accountId} is told the event is full` })
        .toBe(true)
    }
  })
})
