import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import { createSuiteVenue, openBookingRequests, period, retireSuiteVenue } from './support/venue-suite.js'

// SPM-45 in the browser: each role's screens offer only the actions its job needs.
// The API refusals (403) are in spm45-api.spec.js. The suite makes its own venue and
// events, each on its own fixed day, and retires the venue afterwards.

let hall

function tab(page, name) {
  return page.getByRole('navigation').getByText(name, { exact: true })
}

test.describe('SPM-45 Role-Based Feature Access Control (UI)', () => {
  test.beforeAll(async () => {
    hall = await createSuiteVenue('SPM45 UI Hall', { layouts: [{ name: 'Theatre', capacity: 300 }] })
  })

  test.afterAll(async () => {
    await retireSuiteVenue(hall)
  })

  test('TC-SPM45-AC01 Venue Staff can approve and reject booking requests on Booking Requests', async ({ page }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    const sent = await requestVenue(event, hall.venueId, period(1))
    expect(sent.status, JSON.stringify(sent.body)).toBe(201)

    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)

    const card = page.getByTestId(`booking-request-${sent.body.bookingId}`)
    await expect(card.getByRole('button', { name: 'Approve' })).toBeVisible()
    await expect(card.getByRole('button', { name: 'Reject' })).toBeVisible()
  })

  test('TC-SPM45-AC02 Technical Support work with equipment, not venue bookings', async ({ page }) => {
    await login(page, account('TS-01'))

    await expect(tab(page, 'Equipment Catalogue')).toBeVisible()
    await expect(tab(page, 'Reservations')).toBeVisible()
    await expect(tab(page, 'Booking Requests')).toHaveCount(0)
  })

  test('TC-SPM45-AC03 Event Coordinators can request a venue but have no approve or assign controls', async ({
    page,
  }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    await login(page, account('EC-01'))

    await expect(tab(page, 'Venue Requests')).toBeVisible()
    await expect(tab(page, 'Booking Requests')).toHaveCount(0)
    await expect(tab(page, 'Assignments')).toHaveCount(0) // the Lead's tab (SPM-117)

    await page.goto(`/app/events/${event.eventId}/venues`)
    await page.getByTestId(`venue-select-${hall.venueId}`).click()
    await expect(page.getByRole('button', { name: 'Request this venue' })).toBeVisible()
    await expect(page.getByRole('button', { name: /^(Approve|Reject)$/ })).toHaveCount(0)
  })

  test('TC-SPM45-AC04 screens outside a role are not offered to it', async ({ page }) => {
    await login(page, account('VS-01'))

    await expect(tab(page, 'Booking Requests')).toBeVisible()
    for (const name of ['Reservations', 'Assigned Events', 'Assignments', 'Review Queue']) {
      await expect(tab(page, name), name).toHaveCount(0)
    }
  })
})
