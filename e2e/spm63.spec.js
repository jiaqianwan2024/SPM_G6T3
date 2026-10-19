import { test, expect } from '@playwright/test'
import { newEventPayload } from './support/api-data.js'
import { login } from './support/auth.js'
import { eventApi } from './support/event.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import { createSuiteVenue, openBookingRequests, period, retireSuiteVenue, utc } from './support/venue-suite.js'

// The suite makes its own venues and retires them afterwards: a Theatre hall for
// 300, a second Theatre hall, and a room that only offers a Boardroom. Each test
// makes its own event approved for planning and assigned to EC-01 (AC1), on its own
// fixed day, so no test meets another's requests. All times are Singapore time (SGT); the server stores UTC.

let hall
let secondHall
let boardroom

// An event approved for planning on `day`, 10:00 to 12:00.
function eventOn(day, values = {}) {
  const { startsAt, endsAt } = period(day)
  return approvedEvent({ ...THEATRE_EVENT, ...values, proposedStartAt: startsAt, proposedEndAt: endsAt })
}

// The request is for the event's own times.
function request(event, venue, extras = {}) {
  return requestVenue(event, venue.venueId, { startsAt: event.proposedStartAt, endsAt: event.proposedEndAt }, extras)
}

async function bookingsFor(event) {
  const listed = await venueRequest('GET', `/venues/bookings?eventId=${event.eventId}`, 'EC-01')
  expect(listed.status, JSON.stringify(listed.body)).toBe(200)
  return listed.body
}

async function pendingQueue() {
  const queue = await venueRequest('GET', '/venues/bookings?status=pending', 'VS-01')
  expect(queue.status, JSON.stringify(queue.body)).toBe(200)
  return queue.body.map((row) => row.bookingId)
}

test.describe('SPM-63 Submit a venue booking request', () => {
  test.beforeAll(async () => {
    hall = await createSuiteVenue('SPM63 Hall', { layouts: [{ name: 'Theatre', capacity: 300 }] })
    secondHall = await createSuiteVenue('SPM63 Second Hall', { layouts: [{ name: 'Theatre', capacity: 350 }] })
    boardroom = await createSuiteVenue('SPM63 Boardroom', { layouts: [{ name: 'Boardroom', capacity: 20 }] })
  })

  test.afterAll(async () => {
    for (const venue of [hall, secondHall, boardroom]) await retireSuiteVenue(venue)
  })

  test('TC-SPM63-AC01 the assigned coordinator can request a venue for a planning event', async () => {
    const event = await eventOn(1)
    const created = await request(event, hall)

    expect(created.status, JSON.stringify(created.body)).toBe(201)
    expect([created.body.status, created.body.eventId, created.body.venueId]).toEqual([
      'pending',
      event.eventId,
      hall.venueId,
    ])
  })

  test('TC-SPM63-AC01b a request for an event that is not yet assigned to the coordinator is refused', async () => {
    const submitted = await eventApi('POST', '', 'EO-01', newEventPayload(`VENUE-REQ-UNASSIGNED-${Date.now()}`))
    expect(submitted.status, JSON.stringify(submitted.body)).toBe(201)

    const refused = await request(submitted.body, hall)

    expect([refused.status, refused.body.detail]).toEqual([
      403,
      'Only the coordinator assigned to this event can request a venue for it.',
    ])
    expect(await bookingsFor(submitted.body)).toEqual([])
  })

  test('TC-SPM63-AC02 the request carries event facts taken from the event record', async () => {
    const event = await eventOn(2)
    const created = await request(event, secondHall, { coordinatorNotes: 'Please keep the side doors open.' })
    expect(created.status, JSON.stringify(created.body)).toBe(201)

    const viewed = await venueRequest('GET', `/venues/bookings/${created.body.bookingId}`, 'VS-01')

    expect(viewed.status).toBe(200)
    expect(viewed.body.eventSnapshot).toMatchObject({
      eventName: event.eventName,
      expectedAttendance: 50,
      layout: 'Theatre',
      requiredFacilities: 'Stage.',
      accessibilityNeeds: event.accessibilityNeeds,
    })
    expect(viewed.body.eventSnapshot.clientOrganisation).toBeTruthy()
    expect(utc(viewed.body.eventSnapshot.startsAt)).toBe(utc(event.proposedStartAt))
    expect(utc(viewed.body.eventSnapshot.endsAt)).toBe(utc(event.proposedEndAt))
    expect(viewed.body.coordinatorNotes).toBe('Please keep the side doors open.')
  })

  test('TC-SPM63-AC03 a failed suitability check blocks submission', async () => {
    // The room only offers a Boardroom, so a Theatre event fails there.
    const event = await eventOn(3)

    const refused = await request(event, boardroom)

    expect(refused.status).toBe(409)
    expect(refused.body.detail).toMatch(/^This venue is not suitable for this event, so the request cannot be sent\. /)
    expect(refused.body.detail).toContain('Theatre')
    expect(await bookingsFor(event)).toEqual([])
  })

  test('TC-SPM63-AC04 warnings can be submitted after acknowledgement and are carried to venue staff', async ({
    page,
    browser,
  }) => {
    // 280 people in the hall's Theatre (300) is above 90%: a warning, not a failure.
    const event = await eventOn(4, { expectedAttendance: 280 })
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    await page.getByTestId(`venue-select-${hall.venueId}`).click()
    await expect(page.getByTestId('suitability-verdict')).toHaveText(/suitable with warnings/i)
    const send = page.getByRole('button', { name: 'Request this venue' })
    await expect(send).toBeDisabled()

    await page.getByRole('checkbox', { name: /I have read the warnings above/ }).check()
    await send.click()

    await expect(page.getByTestId('venue-request-result')).toHaveText(
      `Request submitted for ${hall.name}. It is now pending with Venue Staff.`,
    )
    const [booking] = await bookingsFor(event)
    expect(JSON.stringify(booking.warnings)).toMatch(/90%/)

    // Venue Staff, in their own browser, see the accepted warning with the request
    // (SPM-8's Booking Requests).
    const staff = await browser.newPage()
    await login(staff, account('VS-01'))
    await openBookingRequests(staff, hall)
    await expect(staff.getByTestId(`booking-request-${booking.bookingId}`)).toContainText('Warnings accepted')
    await expect(staff.getByTestId(`booking-request-${booking.bookingId}`)).toContainText('90%')
    await staff.close()
  })

  test('TC-SPM63-AC05 submitting places the request in the Venue Staff pending queue', async ({ page }) => {
    const event = await eventOn(5)
    const created = await request(event, hall)
    expect(created.status, JSON.stringify(created.body)).toBe(201)

    expect(await pendingQueue()).toContain(created.body.bookingId)
    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)
    const card = page.getByTestId(`booking-request-${created.body.bookingId}`)
    await expect(card).toContainText(`"${event.eventName}"`)
    await expect(card.getByTestId('booking-status')).toHaveText('pending')
    // Venue Staff are also emailed. Email is not stored where a test can read it,
    // so the notifier is covered by the unit tests (notify_venue_staff).
  })

  test('TC-SPM63-AC06 a pending request appears on the calendar and does not make the venue unavailable', async ({
    page,
  }) => {
    const event = await eventOn(6)
    const created = await request(event, hall)
    expect(created.status, JSON.stringify(created.body)).toBe(201)

    const query = `startsAt=${encodeURIComponent(event.proposedStartAt)}&endsAt=${encodeURIComponent(event.proposedEndAt)}`
    const search = await venueRequest('GET', `/venues/search?${query}`, 'EC-01')
    expect(search.body.map((row) => row.venueId)).toContain(hall.venueId)

    await login(page, account('VS-01'))
    await page.goto(`/app/venues/${hall.venueId}/calendar?at=${encodeURIComponent(event.proposedStartAt)}`)
    const entry = page.locator('[data-kind="booking"]', { hasText: event.eventName })
    await expect(entry).toBeVisible()
    await expect(entry).toHaveAttribute('data-status', 'pending')
  })

  test('TC-SPM63-AC07 an event can request a second venue while the first is still pending', async () => {
    // SPM-114 replaced the one-pending-per-event rule. A second venue is allowed;
    // requesting the same venue again while that booking is still live is not.
    const event = await eventOn(7)
    expect((await request(event, hall)).status).toBe(201)

    const second = await request(event, secondHall)
    const same = await request(event, hall)

    expect(second.status, JSON.stringify(second.body)).toBe(201)
    expect([second.body.eventId, second.body.status]).toEqual([event.eventId, 'pending'])
    expect([same.status, same.body.detail]).toEqual([
      409,
      `This event already has a pending booking for ${hall.name}. ` +
        'Withdraw, reject, or cancel that booking before requesting this venue again.',
    ])
  })

  test('TC-SPM63-AC08 the coordinator can withdraw their pending request', async () => {
    const event = await eventOn(8)
    const created = await request(event, hall)
    expect(created.status).toBe(201)

    const byVenueStaff = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/withdraw`, 'VS-01')
    const withdrawn = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/withdraw`, 'EC-01')

    expect(byVenueStaff.status).toBe(403)
    expect([withdrawn.status, withdrawn.body.status]).toEqual([200, 'withdrawn'])
    expect(await pendingQueue()).not.toContain(created.body.bookingId)
  })

  test('TC-SPM63-AC08b a withdrawn request is removed from the venue calendar', async ({ page }) => {
    const event = await eventOn(10)
    const created = await request(event, hall)
    expect(created.status).toBe(201)
    await login(page, account('VS-01'))
    const calendar = `/app/venues/${hall.venueId}/calendar?at=${encodeURIComponent(event.proposedStartAt)}`
    const entry = page.locator('[data-kind="booking"]', { hasText: event.eventName })
    await page.goto(calendar)
    await expect(entry).toHaveAttribute('data-status', 'pending')

    const withdrawn = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/withdraw`, 'EC-01')
    expect(withdrawn.status).toBe(200)
    // Wait until the calendar has its bookings, so "no entry" is checked on loaded data.
    const loaded = page.waitForResponse(
      (response) =>
        response.request().method() === 'GET' &&
        new URL(response.url()).pathname === '/venues/bookings' &&
        new URL(response.url()).searchParams.get('venueId') === hall.venueId,
    )
    await page.goto(calendar)
    await loaded

    await expect(entry).toHaveCount(0)
  })

  test('TC-SPM63-AC09 the readiness view shows the venue arrangement in progress while a request is pending', async ({
    page,
  }) => {
    const event = await eventOn(9)
    await login(page, account('EC-01'))
    // Wait for the readiness answer itself (a condition), since a new event's view
    // gathers venue and equipment details from other services first.
    const readiness = () =>
      page.waitForResponse(
        (response) =>
          response.request().method() === 'GET' && /\/readiness$/.test(new URL(response.url()).pathname),
      )
    let loaded = readiness()
    await page.goto(`/app/events/${event.eventId}/readiness`)
    await loaded
    const venueLine = page
      .getByTestId('readiness-row')
      .filter({ has: page.getByTestId('readiness-category').getByText('venue', { exact: true }) })
    await expect(venueLine.getByTestId('readiness-status')).toHaveText('outstanding')

    expect((await request(event, hall)).status).toBe(201)
    loaded = readiness()
    await page.reload()
    await loaded

    await expect(venueLine.getByTestId('readiness-status')).toHaveText('in progress')
    await page.goto(`/app/events/${event.eventId}/venues`)
    const arrangement = page.getByTestId('venue-arrangement')
    await expect(arrangement).toContainText('Venue arrangements are not complete until every requested venue is approved.')
    await expect(arrangement.getByTestId('venue-booking-pending')).toContainText(`${hall.name} · Pending`)
  })
})
