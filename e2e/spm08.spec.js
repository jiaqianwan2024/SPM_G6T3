import { test, expect } from '@playwright/test'
import { newVenuePayload } from './support/api-data.js'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, freshPeriod, requestVenue } from './support/venue-request.js'

// The suite makes its own hall (30 minutes setup, 45 minutes turnaround, open every
// day) and retires it afterwards, so seeded venues are never approved. Each test sends
// its own requests on a random day years ahead: a 10:00 to 12:00 event occupies the
// hall from 09:30 to 12:45. All times are UTC.

const MINUTE = 60 * 1000
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const HALL_EVENT = { ...THEATRE_EVENT, venueRequirements: 'Projector.', accessibilityNeeds: 'Wheelchair access.' }

let hall

function shift(iso, minutes) {
  return new Date(new Date(iso).getTime() + minutes * MINUTE).toISOString()
}

// The server returns UTC times without a zone marker.
function utc(value) {
  return new Date(/Z|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

function slot(base, fromMinutes, toMinutes) {
  return { startsAt: shift(base.startsAt, fromMinutes), endsAt: shift(base.startsAt, toMinutes) }
}

// The same wording the Booking Requests screen uses.
const day = (value) =>
  new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }).format(utc(value))

async function pending(period) {
  const event = await approvedEvent(HALL_EVENT)
  const sent = await requestVenue(event, hall.venueId, period, { acknowledgeWarnings: true })
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  return { event, booking: sent.body }
}

function approve(booking, accountId = 'VS-01') {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/approve`, accountId, { reason: 'SPM-8 test' })
}

async function read(booking) {
  const got = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
  expect(got.status, JSON.stringify(got.body)).toBe(200)
  return got.body
}

function hold(booking, expiresAt) {
  return venueRequest('POST', `/venues/bookings/${booking.bookingId}/hold`, 'VS-01', { expiresAt })
}

async function block(period) {
  const saved = await venueRequest('POST', `/venues/${hall.venueId}/unavailability`, 'VS-01', {
    ...period,
    reason: 'maintenance',
    note: 'SPM-8 test',
  })
  expect(saved.status, JSON.stringify(saved.body)).toBe(201)
  return saved.body
}

async function hallListed(period) {
  const query = `startsAt=${encodeURIComponent(period.startsAt)}&endsAt=${encodeURIComponent(period.endsAt)}`
  const search = await venueRequest('GET', `/venues/search?${query}`, 'EC-01')
  expect(search.status, JSON.stringify(search.body)).toBe(200)
  return search.body.some((row) => row.venueId === hall.venueId)
}

async function pendingQueue() {
  const queue = await venueRequest('GET', `/venues/bookings?status=pending&venueId=${hall.venueId}`, 'VS-01')
  expect(queue.status, JSON.stringify(queue.body)).toBe(200)
  return queue.body.map((row) => row.bookingId)
}

async function openBookingRequests(page) {
  await login(page, account('VS-01'))
  await page.locator('.nav-item').getByText('Booking Requests', { exact: true }).click()
  await page.getByTestId('booking-venue-filter').selectOption(hall.venueId)
}

const dayBefore = (base) => shift(base.startsAt, -24 * 60)

test.describe('SPM-8 Approve a venue booking request', () => {
  test.beforeAll(async () => {
    const created = await venueRequest('POST', '/venues', 'VS-01', {
      ...newVenuePayload(`AUTO-SPM08 Hall ${Date.now()}`),
      layouts: [{ name: 'Theatre', capacity: 100 }],
      operatingHours: DAYS.map((d) => ({ day: d, opens: '00:00', closes: '24:00' })),
      setupMinutes: 30,
      turnaroundMinutes: 45,
    })
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    hall = created.body
  })

  test.afterAll(async () => {
    if (hall) await venueRequest('POST', `/venues/${hall.venueId}/retire?confirm=true`, 'VS-01')
  })

  test('TC-SPM08-AC01 venue staff view a submitted request with its timing, requirements and submission time', async ({ page }) => {
    const base = freshPeriod()
    const { event, booking } = await pending(base)

    await openBookingRequests(page)
    const card = page.getByTestId(`booking-request-${booking.bookingId}`)
    await expect(card).toBeVisible()
    await expect(card).toContainText(`"${event.eventName}"`)
    await expect(card).toContainText(hall.name)
    await expect(card.getByTestId('booking-status')).toHaveText('pending')
    await expect(card.getByTestId('booking-starts-at')).toHaveText(`${day(base.startsAt)}, 10:00 to 12:00 UTC`)
    await expect(card.getByTestId('booking-occupied')).toContainText(`${day(base.startsAt)}, 09:30 to 12:45 UTC`)
    const requirements = card.getByTestId('booking-requirements')
    await expect(requirements).toContainText('50 attendees')
    await expect(requirements).toContainText('Theatre layout')
    await expect(requirements).toContainText('Facilities: Projector.')
    await expect(requirements).toContainText('Accessibility: Wheelchair access.')
    const created = utc(booking.createdAt)
    const submitted = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
    await expect(card.getByTestId('booking-submitted-at')).toHaveText(
      `${day(booking.createdAt)}, ${submitted.format(created)} UTC`,
    )
  })

  test('TC-SPM08-AC01b only venue staff and coordinators can read the requests', async () => {
    const { booking } = await pending(freshPeriod())

    const organiser = await venueRequest('GET', `/venues/bookings?status=pending&venueId=${hall.venueId}`, 'EO-01')
    expect(organiser.status).toBe(403)
    const one = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'EO-01')
    expect(one.status).toBe(403)
  })

  test('TC-SPM08-AC02 venue staff approve a pending request from Booking Requests', async ({ page }) => {
    const base = freshPeriod()
    const { event, booking } = await pending(base)

    await openBookingRequests(page)
    await page.getByTestId(`booking-approve-note-${booking.bookingId}`).fill('Hall is free that day.')
    await page.getByTestId(`booking-approve-${booking.bookingId}`).click()

    await expect(page.getByTestId('booking-approved-notice')).toHaveText(
      `Approved. ${hall.name} is reserved for "${event.eventName}" from ${day(base.startsAt)}, 09:30 to 12:45 UTC.`,
    )
    await expect(page.getByTestId(`booking-request-${booking.bookingId}`)).toHaveCount(0)
    const after = await read(booking)
    expect([after.status, after.decisionReason]).toEqual(['approved', 'Hall is free that day.'])
  })

  test('TC-SPM08-AC02b only venue staff can approve, and only a booking that exists', async () => {
    const { booking } = await pending(freshPeriod())

    for (const accountId of ['EC-01', 'EO-01']) {
      const refused = await approve(booking, accountId)
      expect(refused.status, accountId).toBe(403)
    }
    expect((await read(booking)).status).toBe('pending')
    const missing = await venueRequest('POST', '/venues/bookings/no-such-booking/approve', 'VS-01', {})
    expect(missing.status).toBe(404)
  })

  test('TC-SPM08-AC03 an approved booking can be viewed and reserves the occupied window', async ({ page }) => {
    const base = freshPeriod()
    const { booking } = await pending(base)
    expect((await approve(booking)).status).toBe(200)

    const shown = await read(booking)
    expect(shown.status).toBe('approved')
    expect([utc(shown.setupStartsAt).toISOString(), utc(shown.teardownEndsAt).toISOString()]).toEqual([
      shift(base.startsAt, -30),
      shift(base.endsAt, 45),
    ])
    expect(await hallListed(slot(base, 150, 180))).toBe(false) // 12:30 to 13:00: inside the turnaround
    expect(await hallListed(slot(base, 195, 240))).toBe(true) // 13:15, set up from 12:45: only touches

    await openBookingRequests(page)
    await page.getByTestId('booking-filter-approved').click()
    const card = page.getByTestId(`booking-request-${booking.bookingId}`)
    await expect(card.getByTestId('booking-status')).toHaveText('approved')
    await expect(card.getByTestId('booking-occupied')).toContainText(`${day(base.startsAt)}, 09:30 to 12:45 UTC`)
    await expect(card).toContainText('Confirmed. The venue is reserved for the occupied window above.')
  })

  test('TC-SPM08-AC04 an approved booking stays locked', async () => {
    const base = freshPeriod()
    const { booking } = await pending(base)
    expect((await approve(booking)).status).toBe(200)

    const again = await approve(booking)
    expect([again.status, again.body.detail]).toEqual([409, 'Booking is already approved'])
    const rejected = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/reject`, 'VS-01', {
      reason: 'SPM-8 test',
    })
    expect([rejected.status, rejected.body.detail]).toEqual([409, 'Booking is already approved'])
    const withdrawn = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/withdraw`, 'EC-01')
    expect(withdrawn.status).toBe(409)
    expect(withdrawn.body.detail).toContain('Only a pending request can be withdrawn')
    const held = await hold(booking, dayBefore(base))
    expect(held.status).toBe(409)

    expect((await read(booking)).status).toBe('approved')
    expect(await hallListed(base)).toBe(false)
  })

  test('TC-SPM08-AC05 approval records who approved it and when, and the record is kept', async ({ page }) => {
    const { booking } = await pending(freshPeriod())
    const before = Date.now()
    const approved = await approve(booking)
    const after = Date.now()

    expect(approved.status, JSON.stringify(approved.body)).toBe(200)
    expect([approved.body.reviewedBy, approved.body.reviewedByName]).toEqual(['u3', 'Vinod Kumar'])
    const when = utc(approved.body.reviewedAt).getTime()
    expect(when).toBeGreaterThanOrEqual(before - MINUTE)
    expect(when).toBeLessThanOrEqual(after + MINUTE)

    const kept = await read(booking)
    expect([kept.reviewedBy, kept.reviewedByName, kept.reviewedAt]).toEqual([
      'u3',
      'Vinod Kumar',
      approved.body.reviewedAt,
    ])

    await openBookingRequests(page)
    await page.getByTestId('booking-filter-approved').click()
    await expect(page.getByTestId(`booking-approved-by-${booking.bookingId}`)).toHaveText(
      `Approved by Vinod Kumar on ${day(kept.reviewedAt)}, ${new Intl.DateTimeFormat('en-GB', {
        timeZone: 'UTC',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
      }).format(utc(kept.reviewedAt))} UTC`,
    )
  })

  test('TC-SPM08-AC06 an overlapping unavailability period blocks approval and the request stays pending', async () => {
    const base = freshPeriod()
    const { booking } = await pending(base) // occupies 09:30 to 12:45
    await block(slot(base, -60, -15)) // 09:00 to 09:45: inside the setup only

    const refused = await approve(booking)
    expect(refused.status).toBe(409)
    expect(refused.body.detail).toMatch(
      new RegExp(`^${hall.name} is unavailable from .* \\(maintenance\\), so this request cannot be approved\\.$`),
    )
    const after = await read(booking)
    expect([after.status, after.reviewedBy, after.reviewedAt]).toEqual(['pending', null, null])
  })

  test('TC-SPM08-AC06b unavailability that only touches the occupied window does not block', async () => {
    const base = freshPeriod()
    const { booking } = await pending(base)
    await block(slot(base, 165, 210)) // 12:45 to 13:30: starts as the turnaround ends

    expect((await approve(booking)).status).toBe(200)
  })

  test('TC-SPM08-AC06c the refusal is shown on Booking Requests and the request stays pending', async ({ page }) => {
    const base = freshPeriod()
    const { booking } = await pending(base)
    await block(slot(base, 150, 180)) // 12:30 to 13:00: inside the turnaround

    await openBookingRequests(page)
    await page.getByTestId(`booking-approve-${booking.bookingId}`).click()

    await expect(page.getByTestId(`booking-error-${booking.bookingId}`)).toContainText(
      `${hall.name} is unavailable from`,
    )
    await expect(page.getByTestId(`booking-error-${booking.bookingId}`)).toContainText(
      'so this request cannot be approved.',
    )
    await expect(page.getByTestId(`booking-request-${booking.bookingId}`).getByTestId('booking-status')).toHaveText(
      'pending',
    )
    expect((await read(booking)).status).toBe('pending')
  })

  test('TC-SPM08-AC07 an overlapping confirmed booking blocks approval and the request stays pending', async () => {
    const base = freshPeriod()
    const a = await pending(base) // 10:00 to 12:00, set up from 09:30
    const b = await pending(slot(base, -180, -60)) // 07:00 to 09:00, turned around until 09:45
    expect((await approve(b.booking)).status).toBe(200)

    const refused = await approve(a.booking)
    expect(refused.status).toBe(409)
    expect(refused.body.detail).toMatch(
      new RegExp(`^${hall.name} is already confirmed for "${b.event.eventName}" at an overlapping time`),
    )
    expect(refused.body.detail).toMatch(/so this request cannot be approved\.$/)
    expect((await read(a.booking)).status).toBe('pending')
    expect((await read(b.booking)).status).toBe('approved')
  })

  test('TC-SPM08-AC08 an overlapping active tentative hold blocks approval and the request stays pending', async () => {
    const base = freshPeriod()
    const a = await pending(base)
    const b = await pending(slot(base, 120, 180)) // 12:00 to 13:00, set up from 11:30
    expect((await hold(b.booking, dayBefore(base))).status).toBe(200)

    const refused = await approve(a.booking)
    expect(refused.status).toBe(409)
    expect(refused.body.detail).toContain(`${hall.name} is on a tentative hold until`)
    expect(refused.body.detail).toContain(`for "${b.event.eventName}"`)
    expect((await read(a.booking)).status).toBe('pending')
    expect((await read(b.booking)).hold.state).toBe('active')
  })

  test('TC-SPM08-AC09 an expired tentative hold does not block approval and is not a confirmed booking', async () => {
    test.setTimeout(180_000)
    const base = freshPeriod()
    const a = await pending(base)
    const b = await pending(slot(base, 120, 180))
    expect((await hold(b.booking, new Date(Date.now() + 65 * 1000).toISOString())).status).toBe(200)
    expect((await approve(a.booking)).status).toBe(409) // still active

    // Let the hold run out on its own; nothing releases it.
    await new Promise((done) => setTimeout(done, 70 * 1000))

    const approved = await approve(a.booking)
    expect([approved.status, approved.body.status]).toEqual([200, 'approved'])
    const expired = await read(b.booking)
    expect([expired.status, expired.hold.state]).toEqual(['pending', 'expired'])
    const confirmed = await venueRequest('GET', `/venues/bookings?status=approved&venueId=${hall.venueId}`, 'VS-01')
    expect(confirmed.body.map((row) => row.bookingId)).not.toContain(b.booking.bookingId)
  })

  test('TC-SPM08-AC10 with no overlap, approval confirms the booking for the event and locks the venue', async () => {
    const base = freshPeriod()
    const a = await pending(base)
    const b = await pending(slot(base, 120, 180)) // 12:00 to 13:00: set up from 11:30, inside A's window
    const c = await pending(slot(base, 195, 240)) // 13:15 to 14:00: set up from 12:45, only touches

    const approved = await approve(a.booking)
    expect(approved.status, JSON.stringify(approved.body)).toBe(200)
    expect([approved.body.status, approved.body.venueId, approved.body.eventId]).toEqual([
      'approved',
      hall.venueId,
      a.event.eventId,
    ])
    const arrangement = await venueRequest('GET', `/venues/bookings?eventId=${a.event.eventId}`, 'EC-01')
    expect(arrangement.body.map((row) => [row.venueId, row.status])).toEqual([[hall.venueId, 'approved']])

    expect((await approve(b.booking)).status).toBe(409)
    expect((await approve(c.booking)).status).toBe(200)
  })

  test('TC-SPM08-AC11 competing requests are shown oldest first and the oldest can be approved first', async ({ page }) => {
    const base = freshPeriod()
    // Submission times are stored to the second, so the requests are sent over a second apart.
    const apart = () => new Promise((done) => setTimeout(done, 1100))
    const first = await pending(base)
    await apart()
    const second = await pending(slot(base, 60, 120)) // 11:00 to 13:00: overlaps the first
    await apart()
    const third = await pending(slot(base, 30, 90)) // 10:30 to 11:30: overlaps both

    const queue = (await pendingQueue()).filter((id) =>
      [first, second, third].some((row) => row.booking.bookingId === id),
    )
    expect(queue).toEqual([first.booking.bookingId, second.booking.bookingId, third.booking.bookingId])

    await openBookingRequests(page)
    await expect(page.getByTestId(`booking-request-${third.booking.bookingId}`)).toBeVisible()
    const ids = await page.locator('[data-testid^="booking-request-"]').evaluateAll((cards) =>
      cards.map((card) => card.dataset.testid.replace('booking-request-', '')),
    )
    expect(ids.filter((id) => queue.includes(id))).toEqual(queue)
    await expect(page.getByTestId(`booking-competing-${first.booking.bookingId}`)).toHaveText('Competing request 1 of 3')
    await expect(page.getByTestId(`booking-competing-${second.booking.bookingId}`)).toHaveText('Competing request 2 of 3')
    await expect(page.getByTestId(`booking-competing-${third.booking.bookingId}`)).toHaveText('Competing request 3 of 3')

    await page.getByTestId(`booking-approve-${first.booking.bookingId}`).click()
    await expect(page.getByTestId('booking-approved-notice')).toBeVisible()
    await expect(page.getByTestId(`booking-request-${first.booking.bookingId}`)).toHaveCount(0)
    expect((await approve(second.booking)).status).toBe(409)
    expect((await approve(third.booking)).status).toBe(409)
  })
})
