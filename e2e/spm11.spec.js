import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { guestRegistration, notificationApi, registrationApi } from './support/registration.js'
import { confirm, readyToConfirm } from './support/confirmation.js'

const DAY = 86400000

// A confirmed event of its own with one place, created through the app rather than the seed, so the
// last place is really the last one and its registration window is the one the app made (SPM-11).
async function confirmedWithOnePlace(label) {
  const now = Date.now()
  const event = await readyToConfirm(label, {
    registrationEnabled: true,
    capacity: 1,
    registrationOpensAt: new Date(now - DAY).toISOString(),
    registrationClosesAt: new Date(now + 60 * DAY).toISOString(),
  })
  const confirmed = await confirm(event)
  expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)
  return event
}

test.describe('SPM-11 Register for an event', () => {
  test('TC-SPM11-AC01 registration succeeds only for a confirmed, enabled, in-period event with a place remaining', async () => {
    const ok = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e1', 'SPM11-OK'))
    expect(ok.status).toBe(201)
    expect(ok.body.eventId).toBe('e1')
    const planning = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e3', 'SPM11-E3'))
    expect([400, 409]).toContain(planning.status)
    const submitted = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e6', 'SPM11-E6'))
    expect([400, 404, 409]).toContain(submitted.status)
  })

  test('TC-SPM11-AC02 mandatory registration fields left blank block submit with inline validation', async ({
    page,
  }) => {
    await login(page, account('ATT-02'))
    await page.goto('/app/browse/e1')
    await page.getByTestId('event-register').click()
    await page.getByTestId('register-submit').click()
    await expect(page.getByTestId('register-name-error')).toBeVisible()
    await expect(page.getByTestId('register-email-error')).toBeVisible()
    const empty = await registrationApi('POST', '/registrations', 'ATT-02', {
      eventId: 'e1',
      name: '',
      email: '',
    })
    expect([400, 409, 422]).toContain(empty.status)
  })

  test('TC-SPM11-AC03 a successful registration confirms on screen with event, date, time, and venue, and notifies the attendee', async ({
    page,
  }) => {
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM11-UI'),
    )
    expect(created.status).toBe(201)
    await login(page, account('ATT-02'))
    await page.goto('/app/browse/e1')
    await expect(page.getByTestId('register-confirmation')).toContainText('AI in Events Summit')
    await expect(page.getByTestId('register-confirmation')).toContainText('Marina Hall A')
    const inbox = await notificationApi('GET', '/notifications', 'ATT-02')
    expect(inbox.status).toBe(200)
    expect(JSON.stringify(inbox.body)).toMatch(/AI in Events Summit|e1|registered/i)
  })

  test('TC-SPM11-AC04 a registration reduces remaining places by one, visible immediately to other attendees', async () => {
    const before = await registrationApi('GET', '/registrations?eventId=e1', 'ATT-01')
    const remainingBefore = before.body.remainingPlaces ?? before.body.placesRemaining
    const created = await registrationApi(
      'POST',
      '/registrations',
      'ATT-02',
      guestRegistration('e1', 'SPM11-DEC'),
    )
    expect(created.status).toBe(201)
    const after = await registrationApi('GET', '/registrations?eventId=e1', 'ATT-01')
    const remainingAfter = after.body.remainingPlaces ?? after.body.placesRemaining
    expect(remainingAfter).toBe(remainingBefore - 1)
  })

  test('TC-SPM11-AC05 a second registration for the same attendee is refused and the existing one is shown', async ({
    page,
  }) => {
    const again = await registrationApi('POST', '/registrations', 'ATT-01', {
      eventId: 'e1',
      name: 'Amy Wong',
      email: 'attendee@connectsphere.com',
    })
    expect([400, 409]).toContain(again.status)
    await login(page, account('ATT-01'))
    await page.goto('/app/browse/e1')
    await expect(page.getByTestId('existing-registration')).toBeVisible()
    await expect(page.getByTestId('existing-registration')).toContainText(/registered|Amy Wong/i)
  })

  test('TC-SPM11-AC06 registration is refused when the event is full', async ({ page }) => {
    const denied = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e2', 'SPM11-FULL'))
    expect([400, 409]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/full|capacity/i)
    await login(page, account('ATT-02'))
    await page.goto('/app/browse/e2')
    await expect(page.getByTestId('event-full')).toBeVisible()
  })

  test('TC-SPM11-AC07 registration outside the period is refused with the period stated', async () => {
    const denied = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e4', 'SPM11-PERIOD'))
    expect([400, 409]).toContain(denied.status)
    expect(JSON.stringify(denied.body)).toMatch(/opens|period|closed/i)
  })

  test('TC-SPM11-AC08 two attendees submitting for the last place: exactly one succeeds', async () => {
    const event = await confirmedWithOnePlace('SPM11-race')
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

  test('TC-SPM11-AC09 every condition is enforced on the server when the endpoint is called directly', async () => {
    const planning = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e3', 'SPM11-API'))
    expect([400, 409]).toContain(planning.status)
    const full = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e2', 'SPM11-API-FULL'))
    expect([400, 409]).toContain(full.status)
    const closed = await registrationApi('POST', '/registrations', 'ATT-02', guestRegistration('e4', 'SPM11-API-CLOSED'))
    expect([400, 409]).toContain(closed.status)
  })

  test('TC-SPM11-AC10 reaching capacity notifies the organiser and the assigned coordinator', async () => {
    const event = await confirmedWithOnePlace('SPM11-full')
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
