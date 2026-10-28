import { test, expect } from '@playwright/test'
import { login, logout } from './support/auth.js'
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

// The suite makes its own hall (Theatre 300, open every day, 30 minutes setup and 45
// turnaround, so a 10:00 to 12:00 event occupies it 09:30 to 12:45) and a second room
// to suggest instead, and retires both afterwards. Each test makes its own events on
// its own fixed day. All times are Singapore time (SGT); the server stores UTC.

let hall
let room

async function pending(when, extras = {}) {
  const event = await approvedEvent(THEATRE_EVENT)
  const sent = await requestVenue(event, hall.venueId, when, { acknowledgeWarnings: true, ...extras })
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  return { event, booking: sent.body }
}

function reject(booking, body, accountId = 'VS-01') {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/reject`, accountId, body)
}

function approve(booking) {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/approve`, 'VS-01', {})
}

async function read(booking) {
  return (await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')).body
}

async function queue() {
  const listed = await venueRequest('GET', `/venues/bookings?status=pending&venueId=${hall.venueId}`, 'VS-01')
  return listed.body.map((row) => row.bookingId)
}

test.describe('SPM-10 Reject a Venue Booking Request', () => {
  test.beforeAll(async () => {
    hall = await createSuiteVenue('SPM10 Hall', {
      layouts: [{ name: 'Theatre', capacity: 300 }],
      setupMinutes: 30,
      turnaroundMinutes: 45,
    })
    room = await createSuiteVenue('SPM10 Riverside Room', { layouts: [{ name: 'Theatre', capacity: 120 }] })
  })

  test.afterAll(async () => {
    for (const venue of [hall, room]) await retireSuiteVenue(venue)
  })

  test('TC-SPM10-AC01 Venue Staff view the full details of a pending request', async ({ page }) => {
    const base = period(1)
    const { event, booking } = await pending(base, { coordinatorNotes: 'Please keep the side doors open.' })

    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)
    const card = page.getByTestId(`booking-request-${booking.bookingId}`)
    await card.getByRole('button', { name: 'View full details' }).click()

    const detail = card.getByTestId(`booking-detail-${booking.bookingId}`)
    // Each value is read from the row with its own label.
    const row = (label) => detail.locator('div').filter({ has: page.getByText(label, { exact: true }) })
    // A row's text is its label followed by its value.
    for (const [label, value] of [
      ['Event', event.eventName],
      ['Venue', hall.name],
      ['Expected attendance', '50'],
      ['Layout', 'Theatre'],
      ['Required facilities', 'Stage.'],
      ['Request notes', booking.requirementsSnapshot],
      ['Coordinator notes', 'Please keep the side doors open.'],
      ['Status', 'pending'],
      ['Tentative hold', 'None'],
    ]) {
      await expect(row(label), label).toHaveText(`${label}${value}`)
    }
    await expect(row('Event times')).toHaveText(/^Event times\d{1,2} \w{3} \d{4}, 10:00 to 12:00 SGT$/)
    await expect(row('Venue occupied')).toHaveText(
      /^Venue occupied\d{1,2} \w{3} \d{4}, 09:30 to 12:45 SGT, including setup and turnaround$/,
    )
    await expect(row('Client organisation')).not.toHaveText('Client organisationNot given')
    await expect(row('Submitted')).toHaveText(/^Submitted\d{1,2} \w{3} \d{4}, \d{2}:\d{2} SGT$/)
    await expect(card.getByRole('button', { name: 'Hide full details' })).toHaveAttribute('aria-expanded', 'true')
  })

  test('TC-SPM10-AC02 rejecting requires a reason, and the request stays pending without one', async ({ page }) => {
    const { booking } = await pending(period(2))

    for (const body of [{}, { reason: '   ' }]) {
      const refused = await reject(booking, body)
      expect([refused.status, refused.body.detail]).toEqual([422, 'Give a reason for rejecting this request.'])
    }
    expect((await read(booking)).status).toBe('pending')

    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)
    const card = page.getByTestId(`booking-request-${booking.bookingId}`)
    await card.getByRole('button', { name: 'Reject' }).click()
    const confirm = card.getByRole('button', { name: 'Confirm rejection' })
    await expect(confirm).toBeDisabled()
    await card.getByLabel('Reason for rejecting (required)').fill('   ')
    await expect(confirm).toBeDisabled()
    await card.getByLabel('Reason for rejecting (required)').fill('Too small for this event.')
    await expect(confirm).toBeEnabled()
  })

  test('TC-SPM10-AC02b only Venue Staff can reject', async () => {
    const { booking } = await pending(period(3))

    for (const accountId of ['EC-01', 'EO-01']) {
      expect((await reject(booking, { reason: 'Not mine to reject.' }, accountId)).status, accountId).toBe(403)
    }
    expect((await read(booking)).status).toBe('pending')
  })

  test('TC-SPM10-AC03 a suggested alternative venue is optional and reaches the coordinator', async ({ page }) => {
    const plain = await pending(period(4))
    const suggestedFor = await pending(slot(period(4), 360, 420)) // 16:00 to 17:00 the same day

    const sameVenue = await reject(suggestedFor.booking, { reason: 'Closed.', suggestedVenueId: hall.venueId })
    expect([sameVenue.status, sameVenue.body.detail]).toEqual([
      422,
      'Suggest a different venue from the one being rejected, or leave the suggestion empty.',
    ])
    const withoutSuggestion = await reject(plain.booking, { reason: 'Closed that week.' })
    expect([withoutSuggestion.status, withoutSuggestion.body.suggestedVenueName]).toEqual([200, null])

    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)
    const card = page.getByTestId(`booking-request-${suggestedFor.booking.bookingId}`)
    await card.getByRole('button', { name: 'Reject' }).click()
    await card.getByLabel('Reason for rejecting (required)').fill('The stage is being rebuilt.')
    await card.getByLabel('Suggest another venue (optional)').selectOption(room.venueId)
    await card.getByRole('button', { name: 'Confirm rejection' }).click()
    await expect(page.getByTestId('booking-approved-notice')).toContainText('Rejected.')
    expect((await read(suggestedFor.booking)).suggestedVenueName).toBe(room.name)

    // The coordinator sees why, and where to try instead, on their Choose venues page.
    const coordinator = page
    await logout(coordinator)
    await login(coordinator, account('EC-01'))
    await coordinator.goto(`/app/events/${suggestedFor.event.eventId}/venues`)
    await expect(coordinator.getByTestId(`venue-rejection-${suggestedFor.booking.bookingId}`)).toContainText(
      `Reason: The stage is being rebuilt. · Suggested instead: ${room.name}`,
    )
  })

  test('TC-SPM10-AC04 a rejected request is Rejected, leaves the queue, and can no longer be approved or changed', async ({
    page,
  }) => {
    const { booking } = await pending(period(5))

    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)
    const card = page.getByTestId(`booking-request-${booking.bookingId}`)
    await card.getByRole('button', { name: 'Reject' }).click()
    await card.getByLabel('Reason for rejecting (required)').fill('Double-booked with a private event.')
    await card.getByRole('button', { name: 'Confirm rejection' }).click()

    await expect(page.getByTestId(`booking-request-${booking.bookingId}`)).toHaveCount(0)
    expect(await queue()).not.toContain(booking.bookingId)
    await page.getByRole('button', { name: 'Rejected', exact: true }).click()
    const rejectedCard = page.getByTestId(`booking-request-${booking.bookingId}`)
    await expect(rejectedCard.getByTestId('booking-status')).toHaveText('rejected')
    await expect(rejectedCard.getByRole('button', { name: 'Approve' })).toHaveCount(0)

    const again = await approve(booking)
    expect([again.status, again.body.detail]).toEqual([409, 'Booking is already rejected'])
    const rejectAgain = await reject(booking, { reason: 'Again.' })
    expect([rejectAgain.status, rejectAgain.body.detail]).toEqual([409, 'Booking is already rejected'])
    expect((await venueRequest('POST', `/venues/bookings/${booking.bookingId}/withdraw`, 'EC-01')).status).toBe(409)
    expect(
      (await venueRequest('POST', `/venues/bookings/${booking.bookingId}/hold`, 'VS-01', {
        expiresAt: shift(utc(booking.startsAt), -24 * 60),
      })).status,
    ).toBe(409)
    expect((await read(booking)).status).toBe('rejected')
  })

  test('TC-SPM10-AC05 a rejected request reserves nothing and its active hold is released', async () => {
    const base = period(6)
    const held = await pending(base)
    const other = await pending(slot(base, 120, 180)) // 12:00 to 13:00, set up from 11:30, inside the held window
    expect(
      (await venueRequest('POST', `/venues/bookings/${held.booking.bookingId}/hold`, 'VS-01', {
        expiresAt: shift(base.startsAt, -24 * 60),
      })).status,
    ).toBe(200)
    expect((await approve(other.booking)).status).toBe(409)

    const rejected = await reject(held.booking, { reason: 'The event no longer fits.' })

    expect([rejected.status, rejected.body.status, rejected.body.hold.state]).toEqual([200, 'rejected', 'rejected'])
    const query = `startsAt=${encodeURIComponent(base.startsAt)}&endsAt=${encodeURIComponent(base.endsAt)}`
    const search = await venueRequest('GET', `/venues/search?${query}`, 'EC-01')
    expect(search.body.map((row) => row.venueId)).toContain(hall.venueId)
    expect((await approve(other.booking)).status).toBe(200)
  })

  test('TC-SPM10-AC06 who rejected the request, the reason, and when are recorded', async ({ page }) => {
    test.slow() // makes an approved event and a request through the API, then checks the Booking Requests page
    const { booking } = await pending(period(7))
    const before = Date.now()
    const rejected = await reject(booking, { reason: 'The stage is being rebuilt.' })
    const after = Date.now()

    expect(rejected.status).toBe(200)
    const stored = await read(booking)
    expect([stored.reviewedBy, stored.reviewedByName, stored.decisionReason]).toEqual([
      'u3',
      'Vinod Kumar',
      'The stage is being rebuilt.',
    ])
    const when = new Date(utc(stored.reviewedAt)).getTime()
    expect(when).toBeGreaterThanOrEqual(before - 60_000)
    expect(when).toBeLessThanOrEqual(after + 60_000)

    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)
    await page.getByRole('button', { name: 'Rejected', exact: true }).click()
    await expect(page.getByTestId(`booking-rejected-by-${booking.bookingId}`)).toContainText(
      'Rejected by Vinod Kumar on',
    )
    await expect(page.getByTestId(`booking-rejection-reason-${booking.bookingId}`)).toHaveText(
      'Reason: The stage is being rebuilt.',
    )
  })

  test('TC-SPM10-AC07 a tentative hold expires at its expiry time, frees the venue, and is not a confirmed booking', async () => {
    test.slow() // waits for a real hold to expire
    const base = period(8)
    const held = await pending(base)
    const other = await pending(slot(base, 120, 180))
    expect(
      (await venueRequest('POST', `/venues/bookings/${held.booking.bookingId}/hold`, 'VS-01', {
        expiresAt: soonExpiry(),
      })).status,
    ).toBe(200)
    expect((await approve(other.booking)).status).toBe(409) // still active

    await waitForHoldToExpire(held.booking.bookingId)

    expect((await approve(other.booking)).status).toBe(200)
    const expired = await read(held.booking)
    expect([expired.status, expired.hold.state]).toEqual(['pending', 'expired'])
    const confirmed = await venueRequest('GET', `/venues/bookings?status=approved&venueId=${hall.venueId}`, 'VS-01')
    expect(confirmed.body.map((row) => row.bookingId)).not.toContain(held.booking.bookingId)
  })

  test('TC-SPM10-AC08 a pending request without a hold stays in the queue until Venue Staff approve or reject it', async () => {
    const base = period(9)
    const waiting = await pending(base)
    const approved = await pending(slot(base, 300, 360)) // 15:00 to 16:00, clear of the first
    const rejected = await pending(slot(base, 480, 540)) // 18:00 to 19:00

    expect((await approve(approved.booking)).status).toBe(200)
    expect((await reject(rejected.booking, { reason: 'Not suitable.' })).status).toBe(200)

    const listed = await queue()
    expect(listed).toContain(waiting.booking.bookingId)
    expect(listed).not.toContain(approved.booking.bookingId)
    expect(listed).not.toContain(rejected.booking.bookingId)
    expect([(await read(waiting.booking)).status, (await read(waiting.booking)).hold]).toEqual(['pending', null])

    expect((await approve(waiting.booking)).status).toBe(200)
    expect(await queue()).not.toContain(waiting.booking.bookingId)
  })
})
