import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import {
  createSuiteVenue,
  openBookingRequests,
  period,
  retireSuiteVenue,
  shift,
  slot,
  soonExpiry,
  utc,
  waitForHoldToExpire,
} from './support/venue-suite.js'

// The suite's own hall needs 30 minutes of setup and 60 of turnaround, so a 10:00 to
// 12:00 booking occupies it from 09:30 to 13:00. Each test books its own fixed day
// on it, so no test meets another's bookings or an earlier run's. All times are UTC.

let hall

// A pending request for a new event approved for planning. Later requests at an
// overlapping time carry a warning about the earlier one, so they acknowledge it.
async function pending(when) {
  const event = await approvedEvent(THEATRE_EVENT)
  const sent = await requestVenue(event, hall.venueId, when, { acknowledgeWarnings: true })
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  return { event, booking: sent.body }
}

// SPM-9: Venue Staff record an unavailability block; tests remove theirs afterwards.
async function block(startsAt, endsAt, note) {
  const saved = await venueRequest('POST', `/venues/${hall.venueId}/unavailability`, 'VS-01', {
    startsAt,
    endsAt,
    reason: 'maintenance',
    note,
  })
  expect(saved.status, JSON.stringify(saved.body)).toBe(201)
  return saved.body
}

function unblock(saved) {
  return venueRequest('DELETE', `/venues/${hall.venueId}/unavailability/${saved.unavailabilityId}`, 'VS-01')
}

// SPM-116: Venue Staff hold a pending request until `expiresAt`.
function hold(booking, expiresAt) {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/hold`, 'VS-01', { expiresAt })
}

function approve(booking) {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/approve`, 'VS-01', { reason: 'SPM-64 test' })
}

async function status(booking) {
  return (await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')).body.status
}

test.describe('SPM-64 Prevent double-booking of a venue', () => {
  test.beforeAll(async () => {
    hall = await createSuiteVenue('SPM64 Hall', {
      layouts: [{ name: 'Theatre', capacity: 300 }],
      setupMinutes: 30,
      turnaroundMinutes: 60,
    })
  })

  test.afterAll(async () => {
    await retireSuiteVenue(hall)
  })

  test('TC-SPM64-AC01 search, suitability, and approval apply the same rule', async () => {
    const base = period(1)
    const first = await pending(base)
    const second = await pending(slot(base, 150, 240)) // 12:30 to 14:00
    expect((await approve(first.booking)).status).toBe(200)

    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(shift(base.startsAt, 150))}&endsAt=${encodeURIComponent(shift(base.startsAt, 240))}`,
      'EC-01',
    )
    const suitability = await venueRequest('POST', '/venues/suitability', 'EC-01', {
      eventId: second.event.eventId,
      venueId: hall.venueId,
      ...slot(base, 150, 240),
    })
    const approval = await approve(second.booking)

    expect(search.status).toBe(200)
    expect(search.body.map((row) => row.venueId)).not.toContain(hall.venueId)
    expect(suitability.body.verdict).toBe('not suitable')
    expect(approval.status).toBe(409)
  })

  test('TC-SPM64-AC02 the occupied window adds the venue setup and turnaround time', async () => {
    const base = period(2)
    const { booking } = await pending(base)

    expect(utc(booking.setupStartsAt)).toBe(shift(base.startsAt, -30))
    expect(utc(booking.teardownEndsAt)).toBe(shift(base.endsAt, 60))
  })

  test('TC-SPM64-AC03 a second overlapping booking cannot be confirmed and the clash is named', async () => {
    const base = period(3)
    const first = await pending(base)
    const second = await pending(slot(base, 60, 180))
    expect((await approve(first.booking)).status).toBe(200)

    const refused = await approve(second.booking)

    expect(refused.status).toBe(409)
    expect(refused.body.detail).toContain(`${hall.name} is already confirmed for "${first.event.eventName}"`)
    expect(await status(second.booking)).toBe('pending')
    // The database refusing an overlap on its own is proven in
    // services/venue-service/tests/integration/test_double_booking_mysql.py.
  })

  test('TC-SPM64-AC03b Venue Staff are shown the clash on Booking Requests and the request stays pending', async ({
    page,
  }) => {
    const base = period(4)
    const first = await pending(base)
    const second = await pending(slot(base, 60, 180)) // 11:00 to 13:00, inside the first's window
    expect((await approve(first.booking)).status).toBe(200)

    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)
    const card = page.getByTestId(`booking-request-${second.booking.bookingId}`)
    await card.getByRole('button', { name: 'Approve' }).click()

    await expect(card).toContainText(`${hall.name} is already confirmed for "${first.event.eventName}"`)
    await expect(card).toContainText('so this request cannot be approved.')
    await expect(card.getByTestId('booking-status')).toHaveText('pending')
    expect(await status(second.booking)).toBe('pending')
  })

  test('TC-SPM64-AC04 a confirmed booking conflicts with an overlapping unavailability period', async () => {
    const base = period(5)
    const { booking } = await pending(base) // occupies 09:30 to 13:00
    const saved = await block(shift(base.endsAt, 30), shift(base.endsAt, 60), 'SPM-64 AC4') // inside the turnaround
    try {
      const refused = await approve(booking)

      expect(refused.status).toBe(409)
      expect(refused.body.detail).toMatch(
        new RegExp(`^${hall.name} is unavailable from .+ \\(maintenance\\), so this request cannot be approved\\.$`),
      )
    } finally {
      await unblock(saved)
    }
    expect((await approve(booking)).status).toBe(200)
  })

  test('TC-SPM64-AC04 a booking cannot be confirmed over an active tentative hold', async () => {
    const base = period(6)
    const first = await pending(base)
    const second = await pending(slot(base, 120, 180)) // starts as the first ends, set up from 11:30
    const held = await hold(first.booking, shift(base.startsAt, -24 * 60))
    expect(held.status, JSON.stringify(held.body)).toBe(200)

    const refused = await approve(second.booking)

    expect(refused.status).toBe(409)
    expect(refused.body.detail).toContain(`${hall.name} is on a tentative hold until`)
    expect(refused.body.detail).toContain(`for "${first.event.eventName}"`)
    expect(await status(second.booking)).toBe('pending')
  })

  test('TC-SPM64-AC05 an expired tentative hold does not conflict and is not a confirmed booking', async () => {
    test.slow() // waits for a real hold to expire
    const base = period(7)
    const first = await pending(base)
    const second = await pending(slot(base, 120, 180))
    expect((await hold(first.booking, soonExpiry())).status).toBe(200)
    expect((await approve(second.booking)).status).toBe(409)

    await waitForHoldToExpire(first.booking.bookingId)

    expect(await status(first.booking)).toBe('pending')
    expect((await approve(second.booking)).status).toBe(200)
  })

  test('TC-SPM64-AC06 touching windows are fine, touching event times can still clash', async () => {
    const base = period(8)
    const first = await pending(base)
    const touchingWindow = await pending(slot(base, 210, 240)) // 13:30 to 14:00, set up from 13:00
    const touchingTimes = await pending(slot(base, 120, 180)) // 12:00 to 13:00, set up from 11:30
    expect((await approve(first.booking)).status).toBe(200)

    expect((await approve(touchingWindow.booking)).status).toBe(200)
    expect((await approve(touchingTimes.booking)).status).toBe(409)
  })

  test('TC-SPM64-AC07 two approvals for clashing requests at once: exactly one succeeds', async () => {
    const base = period(9)
    const a = await pending(base)
    const b = await pending(slot(base, 30, 150))

    const results = await Promise.all([approve(a.booking), approve(b.booking)])

    expect(results.map((result) => result.status).sort()).toEqual([200, 409])
    expect(results.find((result) => result.status === 409).body.detail).toMatch(/cannot be approved\.$/)
  })

  test('TC-SPM64-AC08 withdrawing, cancelling a booking, or cancelling the event frees the venue', async () => {
    // Withdrawing (SPM-63) a pending request.
    const base = period(10)
    const first = await pending(base)
    const withdrawn = await venueRequest('POST', `/venues/bookings/${first.booking.bookingId}/withdraw`, 'EC-01')
    expect(withdrawn.status, JSON.stringify(withdrawn.body)).toBe(200)
    const second = await pending(base)
    expect((await approve(second.booking)).status).toBe(200)

    // Cancelling that one confirmed booking (SPM-114) frees the period.
    const cancelled = await venueRequest('POST', `/venues/bookings/${second.booking.bookingId}/cancel`, 'VS-01')
    expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200)
    const third = await pending(base)
    expect((await approve(third.booking)).status).toBe(200)

    // Cancelling the event releases all its bookings (SPM-114's release, which
    // event cancellation in SPM-88 is to call).
    const released = await venueRequest('POST', '/venues/bookings/release', 'EC-01', { eventId: third.event.eventId })
    expect(released.status, JSON.stringify(released.body)).toBe(200)
    expect(released.body.map((row) => row.status)).toEqual(['cancelled'])
    const fourth = await pending(base)
    expect((await approve(fourth.booking)).status).toBe(200)
  })
})
