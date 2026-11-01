import { expect } from '@playwright/test'
import { newVenuePayload } from './api-data.js'
import { venueRequest } from './venue.js'

// Test data for the venue booking suites (SPM-8, 61 to 64, 112, 116, 122), kept to
// the FIRST principles:
// - Isolated: each suite books only a venue it creates in beforeAll and retires in
//   afterAll, so it never meets bookings another suite or an earlier run left behind.
// - Repeatable: no random dates. Each test passes its own fixed day number, worked
//   out from a date taken once per run, so a run that crosses midnight UTC still
//   uses the same days.
// - Fast: waiting for a hold to expire polls for the condition instead of sleeping.

const MINUTE = 60 * 1000
const DAY = 24 * 60 * MINUTE
const START_OF_TODAY = (() => {
  const today = new Date()
  today.setUTCHours(0, 0, 0, 0)
  return today.getTime()
})()

export const EVERY_DAY = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => ({
  day,
  opens: '00:00',
  closes: '24:00',
}))

// 10:00 Singapore time (02:00 UTC), `day` days from today, for `hours` hours. Days start at 400 so every
// period is well in the future, and an expiry a day before it is still ahead.
export function period(day, hours = 2) {
  const start = START_OF_TODAY + (400 + day) * DAY + 2 * 60 * MINUTE
  return { startsAt: new Date(start).toISOString(), endsAt: new Date(start + hours * 60 * MINUTE).toISOString() }
}

export function shift(iso, minutes) {
  return new Date(new Date(iso).getTime() + minutes * MINUTE).toISOString()
}

// A period relative to `base`'s start, e.g. slot(base, 120, 180) is 12:00 to 13:00.
export function slot(base, fromMinutes, toMinutes) {
  return { startsAt: shift(base.startsAt, fromMinutes), endsAt: shift(base.startsAt, toMinutes) }
}

// The server returns UTC times without a zone marker.
export function utc(value) {
  return new Date(/Z|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toISOString()
}

// A time as a datetime-local value in Singapore time (UTC + 8 hours), as the screens show it.
export function sgtInput(value) {
  return shift(utc(value), 8 * 60).slice(0, 16)
}

// A venue for one suite only. The values a test depends on are passed in, so they
// are visible in the spec; the rest are newVenuePayload's defaults.
export async function createSuiteVenue(label, values) {
  const created = await venueRequest('POST', '/venues', 'VS-01', {
    ...newVenuePayload(`AUTO-${label} ${Date.now()}`),
    operatingHours: EVERY_DAY,
    ...values,
  })
  expect(created.status, JSON.stringify(created.body)).toBe(201)
  return created.body
}

export async function retireSuiteVenue(venue) {
  if (venue) await venueRequest('POST', `/venues/${venue.venueId}/retire?confirm=true`, 'VS-01')
}

// A hold expiring in about 15 seconds: long enough for the checks made while it is
// active, short enough that waiting for it to expire costs little. Tests that wait
// for it call test.slow(), Playwright's mark for a test known to take longer.
export function soonExpiry(seconds = 15) {
  return new Date(Date.now() + seconds * 1000).toISOString()
}

// Wait for the hold to expire on the server: poll the condition, never a fixed sleep.
export async function waitForHoldToExpire(bookingId) {
  await expect
    .poll(
      async () => (await venueRequest('GET', `/venues/bookings/${bookingId}`, 'VS-01')).body?.hold?.state,
      { timeout: 60_000, intervals: [2_000] },
    )
    .toBe('expired')
}

// Sign in and open the Venue Staff "Booking Requests" tab for one venue, finding
// the controls by role and label the way a user would.
export async function openBookingRequests(page, venue) {
  await page.getByRole('navigation').getByText('Booking Requests', { exact: true }).click()
  // The select sits inside its label, so its accessible name also holds the options' text.
  await page.getByTestId('booking-requests').getByLabel('Venue').selectOption(venue.venueId)
}
