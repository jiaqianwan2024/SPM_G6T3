import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { createSubmittedEvent, eventApi, raiseChangeRequest } from './support/event.js'
import { bookVenue, planningEvent } from './support/confirmation.js'

// SPM-55: each test makes the events it reads, assigned to EC-01, so seed data that earlier runs
// changed cannot decide the result. Each section reads every assigned event, so on a database
// that test runs have filled the sections fill in slowly; LOADED gives them the time.
const LOADED = { timeout: 60_000 }
test.describe.configure({ timeout: 120_000 })

async function openDashboard(page, accountId = 'EC-01') {
  await login(page, account(accountId))
  await expect(page.getByTestId('coordinator-home')).toBeVisible()
}

test.describe('SPM-55 Event Coordinator dashboard', () => {
  test('TC-SPM55-AC01 the coordinator sees their own events with status and what is still outstanding', async ({
    page,
  }) => {
    const event = await planningEvent('SPM55-own')
    await openDashboard(page)
    const item = page.getByTestId(`coordinator-event-${event.eventId}`)
    await expect(item).toBeVisible()
    await expect(item).toContainText(event.eventName)
    await expect(page.getByTestId(`coordinator-event-${event.eventId}-status`)).toBeVisible()
    // Planning with no venue booked yet, so the venue is outstanding.
    await expect(page.getByTestId(`coordinator-event-${event.eventId}-outstanding`)).toContainText(/venue/i, LOADED)
  })

  test('TC-SPM55-AC02 unassigned submitted requests are not shown here', async ({ page }) => {
    const unassigned = await createSubmittedEvent('EO-01', `AUTO-SPM55-unassigned-${Date.now()}`)
    await openDashboard(page)
    await expect(page.getByTestId('coordinator-section-events')).toBeVisible()
    await expect(page.getByTestId(`coordinator-event-${unassigned.eventId}`)).toHaveCount(0)
  })

  test('TC-SPM55-AC03 change requests awaiting the coordinator are shown newest first', async ({ page }) => {
    const older = await planningEvent('SPM55-older')
    const newer = await planningEvent('SPM55-newer')
    const first = await raiseChangeRequest(older.eventId, 'EO-01', {
      reason: 'AUTO-SPM55 older',
      proposedChanges: { description: 'Older change' },
    })
    expect(first.status, JSON.stringify(first.body)).toBe(201)
    const second = await raiseChangeRequest(newer.eventId, 'EO-01', {
      reason: 'AUTO-SPM55 newer',
      proposedChanges: { description: 'Newer change' },
    })
    expect(second.status, JSON.stringify(second.body)).toBe(201)

    await openDashboard(page)
    const section = page.getByTestId('coordinator-section-changes')
    await expect(section.getByTestId(`coordinator-change-${first.body.changeRequestId}`)).toBeVisible(LOADED)
    await expect(section.getByTestId(`coordinator-change-${second.body.changeRequestId}`)).toBeVisible(LOADED)
    const ids = await section.locator('[data-testid^="coordinator-change-"]').evaluateAll((rows) =>
      rows.map((row) => row.getAttribute('data-testid')),
    )
    const newerAt = ids.indexOf(`coordinator-change-${second.body.changeRequestId}`)
    const olderAt = ids.indexOf(`coordinator-change-${first.body.changeRequestId}`)
    expect(newerAt).toBeGreaterThanOrEqual(0)
    expect(olderAt).toBeGreaterThan(newerAt)
  })

  test('TC-SPM55-AC04 arrangements flagged for re-verification are shown prominently', async ({ page }) => {
    const event = await planningEvent('SPM55-reverify')
    const booking = await bookVenue(event)
    const changed = await eventApi('PATCH', `/${event.eventId}`, 'EC-01', {
      expectedAttendance: 45,
      confirmSignificantChange: true,
    })
    expect(changed.status, JSON.stringify(changed.body)).toBe(200)

    await openDashboard(page)
    const flag = page.getByTestId(`coordinator-reverify-booking-${booking.bookingId}`)
    await expect(flag).toBeVisible(LOADED)
    await expect(flag).toContainText(event.eventName)
    // The re-verification section comes before the other lists.
    const order = await page.locator('[data-testid^="coordinator-section-"]').evaluateAll((sections) =>
      sections.map((section) => section.getAttribute('data-testid')),
    )
    expect(order[0]).toBe('coordinator-section-reverify')
  })

  test('TC-SPM55-AC05 every item opens the screen where the work is done', async ({ page }) => {
    const event = await planningEvent('SPM55-link')
    await openDashboard(page)
    await page.getByTestId(`coordinator-event-${event.eventId}`).click()
    await expect(page).toHaveURL(new RegExp(`/app/events/${event.eventId}$`))
  })

  test('TC-SPM55-AC06 lists follow the same access rules: another coordinator does not see these events', async ({
    page,
  }) => {
    const event = await planningEvent('SPM55-mine')
    await openDashboard(page, 'EC-02')
    await expect(page.getByTestId('coordinator-section-events')).toBeVisible()
    await expect(page.getByTestId(`coordinator-event-${event.eventId}`)).toHaveCount(0)
  })

  test('TC-SPM55-AC07 each section has an empty state saying there is nothing to do', async ({ page }) => {
    // A coordinator with no events assigned: every section is empty.
    await page.route('**/events/assigned*', (route) => route.fulfill({ json: [] }))
    await openDashboard(page)
    await expect(page.getByTestId('coordinator-events-empty')).toBeVisible()
    await expect(page.getByTestId('coordinator-changes-empty')).toBeVisible()
    await expect(page.getByTestId('coordinator-reverify-empty')).toBeVisible()
  })
})
