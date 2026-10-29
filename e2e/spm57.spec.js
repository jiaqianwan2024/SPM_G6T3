import { test, expect } from '@playwright/test'
import { serviceUrls } from './support/api-data.js'
import { authedApi, login } from './support/auth.js'
import { account } from './support/test-data.js'
import { releaseBooking, venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import { createSuiteVenue, period, retireSuiteVenue } from './support/venue-suite.js'

// SPM-57: Venue Staff's home screen. The suite makes its own venue and, on it, one
// booking per list: a pending request (far ahead), an approved booking flagged for
// re-verification (far ahead), and an approved booking two days from now. It frees
// the bookings and retires the venue afterwards, so nothing depends on seeded data.

const DAY = 24 * 60 * 60 * 1000

let hall
let pending
let flagged
let soon

// 10:00 to 12:00 Singapore time (02:00 to 04:00 UTC), two days from today: inside the next 7 days.
function inTwoDays() {
  const start = new Date()
  start.setUTCHours(2, 0, 0, 0)
  const startsAt = new Date(start.getTime() + 2 * DAY)
  return { startsAt: startsAt.toISOString(), endsAt: new Date(startsAt.getTime() + 2 * 60 * 60 * 1000).toISOString() }
}

// "19 Oct 2026, 10:00 to 12:00 SGT": a booking's event time as the dashboard writes it.
function sgtRange({ startsAt, endsAt }) {
  const day = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', day: 'numeric', month: 'short', year: 'numeric' })
  const time = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
  return `${day.format(new Date(startsAt))}, ${time.format(new Date(startsAt))} to ${time.format(new Date(endsAt))} SGT`
}

async function booking(name, when, approve) {
  const event = await approvedEvent({ ...THEATRE_EVENT, eventName: `AUTO-SPM57-${name}-${Date.now()}`, proposedStartAt: when.startsAt, proposedEndAt: when.endsAt })
  const sent = await requestVenue(event, hall.venueId, when)
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  if (approve) {
    const approved = await venueRequest('POST', `/venues/bookings/${sent.body.bookingId}/approve`, 'VS-01', {})
    expect(approved.status, JSON.stringify(approved.body)).toBe(200)
  }
  return { ...sent.body, event, when }
}

test.describe('SPM-57 Venue Staff dashboard', () => {
  test.beforeAll(async () => {
    // Three events, each created, assigned and approved, then booked: more than one test's time.
    test.setTimeout(180_000)
    // 30 minutes setup, so a 10:00 event is set up from 09:30.
    hall = await createSuiteVenue('SPM57 Hall', { layouts: [{ name: 'Theatre', capacity: 300 }], setupMinutes: 30 })
    pending = await booking('PENDING', period(1), false)
    flagged = await booking('FLAGGED', period(2), true)
    const marked = await venueRequest('POST', '/venues/bookings/reverification', 'EC-01', {
      eventId: flagged.event.eventId,
      reason: 'Expected attendance: 50 -> 280',
    })
    expect(marked.status, JSON.stringify(marked.body)).toBe(200)
    soon = await booking('SOON', inTwoDays(), true)
  })

  test.afterAll(async () => {
    for (const row of [pending, flagged, soon]) if (row) await releaseBooking(row.bookingId)
    await retireSuiteVenue(hall)
  })

  test('TC-SPM57-AC01 pending booking requests show the event, requested venue, and requested date and time', async ({ page }) => {
    await login(page, account('VS-01'))

    const item = page.getByTestId(`venue-pending-${pending.bookingId}`)
    await expect(item).toContainText(pending.event.eventName)
    await expect(item).toContainText(hall.name)
    await expect(item.getByTestId(`venue-pending-${pending.bookingId}-datetime`)).toHaveText(sgtRange(pending.when))
    // Decided requests are not waiting on Venue Staff.
    await expect(page.getByTestId(`venue-pending-${soon.bookingId}`)).toHaveCount(0)
  })

  test('TC-SPM57-AC02 bookings flagged for re-verification are shown with what changed', async ({ page }) => {
    await login(page, account('VS-01'))

    const item = page.getByTestId(`venue-reverification-${flagged.bookingId}`)
    await expect(item).toContainText(flagged.event.eventName)
    await expect(item).toContainText('Expected attendance: 50 -> 280')
    await expect(page.getByTestId(`venue-reverification-${soon.bookingId}`)).toHaveCount(0)
  })

  test('TC-SPM57-AC03 confirmed bookings in the next few days are shown, with the setup time', async ({ page }) => {
    await login(page, account('VS-01'))

    const item = page.getByTestId(`venue-upcoming-${soon.bookingId}`)
    await expect(item).toContainText(soon.event.eventName)
    await expect(item).toContainText(hall.name)
    await expect(item).toContainText(sgtRange(soon.when))
    await expect(item).toContainText('Setup from 09:30')
    // A year ahead is not "the next few days" (boundary).
    await expect(page.getByTestId(`venue-upcoming-${flagged.bookingId}`)).toHaveCount(0)
  })

  test('TC-SPM57-AC04 every item opens the screen where the work is done', async ({ page }) => {
    test.slow()
    await login(page, account('VS-01'))

    await page.getByTestId(`venue-pending-${pending.bookingId}`).click()
    await expect(page).toHaveURL(new RegExp(`booking=${pending.bookingId}`))
    await expect(page.getByTestId(`booking-request-${pending.bookingId}`).getByRole('button', { name: 'Approve' })).toBeVisible()

    await page.goto('/app')
    await page.getByTestId(`venue-reverification-${flagged.bookingId}`).click()
    await expect(page).toHaveURL(new RegExp(`booking=${flagged.bookingId}`))
    await expect(page.getByTestId(`booking-request-${flagged.bookingId}`).getByTestId('booking-reconfirm')).toBeVisible()

    await page.goto('/app')
    await page.getByTestId(`venue-upcoming-${soon.bookingId}`).click()
    await expect(page).toHaveURL(/tab=Venue\+Calendar/)
    await expect(page).toHaveURL(new RegExp(`venue=${hall.venueId}`))
    await expect(page.getByTestId('venue-calendar')).toBeVisible()
  })

  test('TC-SPM57-AC05 the lists obey the same access rules as the Booking Requests screen', async ({ page }) => {
    for (const id of ['EC-01', 'ECL-01', 'EO-01', 'TS-01', 'SO-01', 'ATT-01']) {
      const refused = await authedApi('GET', `${serviceUrls.venue}/venues/dashboard`, id)
      expect(refused.status, id).toBe(403)
    }
    const allowed = await authedApi('GET', `${serviceUrls.venue}/venues/dashboard`, 'VS-02')
    expect(allowed.status).toBe(200)
    expect(allowed.body.pending.map((row) => row.bookingId)).toContain(pending.bookingId)

    await login(page, account('EC-01'))
    await expect(page.getByTestId('venue-dashboard')).toHaveCount(0)
  })

  test('TC-SPM57-AC06 each section has an empty state', async ({ page }) => {
    // Stand in for a day with nothing on: the screen's empty states, not the server's data.
    await page.route('**/venues/dashboard', (route) =>
      route.fulfill({ json: { pending: [], reverification: [], upcoming: [], upcomingDays: 7 } }),
    )
    await login(page, account('VS-01'))

    await expect(page.getByTestId('venue-pending-empty')).toBeVisible()
    await expect(page.getByTestId('venue-reverification-empty')).toBeVisible()
    await expect(page.getByTestId('venue-upcoming-empty')).toBeVisible()
  })
})
