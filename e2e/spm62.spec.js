import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import { createSuiteVenue, period, retireSuiteVenue, slot } from './support/venue-suite.js'

// The suite makes its own venues and retires them afterwards:
// - a hall: Theatre for 300, open every day, Stage, PA system and Projector,
//   wheelchair accessible;
// - a boardroom: Boardroom for 20 only, open every day 08:00 to 18:00 UTC, no
//   facilities or accessibility features.
// Each test uses its own events on its own fixed day. All times are UTC.

let hall
let boardroom

// An event approved for planning on `day`, 10:00 to 12:00.
function eventOn(day, values = {}) {
  const { startsAt, endsAt } = period(day)
  return approvedEvent({ ...THEATRE_EVENT, ...values, proposedStartAt: startsAt, proposedEndAt: endsAt })
}

async function check(event, venue, extras = {}) {
  const result = await venueRequest('POST', '/venues/suitability', 'EC-01', {
    eventId: event.eventId,
    venueId: venue.venueId,
    ...extras,
  })
  expect(result.status, JSON.stringify(result.body)).toBe(200)
  return result.body
}

const messages = (result, severity) =>
  result.reasons.filter((reason) => reason.severity === severity).map((reason) => reason.message)

test.describe('SPM-62 Venue suitability check for an event', () => {
  test.beforeAll(async () => {
    hall = await createSuiteVenue('SPM62 Hall', {
      layouts: [{ name: 'Theatre', capacity: 300 }],
      facilities: ['Stage', 'PA system', 'Projector'],
      accessibility: ['Wheelchair accessible'],
    })
    boardroom = await createSuiteVenue('SPM62 Boardroom', {
      layouts: [{ name: 'Boardroom', capacity: 20 }],
      operatingHours: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => ({
        day,
        opens: '08:00',
        closes: '18:00',
      })),
      facilities: [],
      accessibility: [],
    })
  })

  test.afterAll(async () => {
    for (const venue of [hall, boardroom]) await retireSuiteVenue(venue)
  })

  test('TC-SPM62-AC01 the check returns suitable, suitable with warnings, or not suitable with reasons', async () => {
    const fits = await check(await eventOn(1), hall)
    const tight = await check(await eventOn(2, { expectedAttendance: 280 }), hall)
    const wrongLayout = await check(await eventOn(3), boardroom)

    expect([fits.verdict, fits.reasons]).toEqual(['suitable', []])
    expect([tight.verdict, messages(tight, 'warning').length, messages(tight, 'failure')]).toEqual([
      'suitable with warnings',
      1,
      [],
    ])
    expect(wrongLayout.verdict).toBe('not suitable')
    expect(messages(wrongLayout, 'failure')).toEqual([
      'This venue does not offer the Theatre layout. Layouts offered: Boardroom.',
    ])
  })

  test('TC-SPM62-AC02 attendance above layout capacity is a failure that names both numbers', async () => {
    const result = await check(await eventOn(4), boardroom, { expectedAttendance: 500, layout: 'Boardroom' })

    expect(result.verdict).toBe('not suitable')
    expect(messages(result, 'failure')).toEqual([
      'Expected attendance of 500 is more than this venue can hold in the Boardroom layout (20 people).',
    ])
  })

  test('TC-SPM62-AC02b attendance equal to the layout capacity is not a failure', async () => {
    const result = await check(await eventOn(5), boardroom, { expectedAttendance: 20, layout: 'Boardroom' })

    expect(messages(result, 'failure')).toEqual([])
  })

  test('TC-SPM62-AC03 unsupported layout, missing facility, and missing accessibility are named failures', async () => {
    const result = await check(await eventOn(6), boardroom, {
      layout: 'Exhibition',
      requiredFacilities: ['Loading dock'],
      requiredAccessibility: ['Hearing loop'],
    })

    expect(result.verdict).toBe('not suitable')
    expect(messages(result, 'failure')).toEqual(
      expect.arrayContaining([
        'This venue does not offer the Exhibition layout. Layouts offered: Boardroom.',
        'Required facility not available at this venue: Loading dock.',
        'Required accessibility feature not available at this venue: Hearing loop.',
      ]),
    )
  })

  test('TC-SPM62-AC04 an overlapping confirmed booking is a named failure', async () => {
    const booked = await eventOn(7)
    const sent = await requestVenue(booked, hall.venueId, period(7))
    expect(sent.status, JSON.stringify(sent.body)).toBe(201)
    const approved = await venueRequest('POST', `/venues/bookings/${sent.body.bookingId}/approve`, 'VS-01', {})
    expect(approved.status, JSON.stringify(approved.body)).toBe(200)

    const result = await check(await eventOn(7), hall)

    expect(result.verdict).toBe('not suitable')
    const [clash] = result.reasons.filter((reason) => reason.check === 'clash')
    expect(clash.severity).toBe('failure')
    expect(clash.message).toMatch(
      new RegExp(`^This venue already has a confirmed booking for "${booked.eventName}" at an overlapping time `),
    )
  })

  test('TC-SPM62-AC04 an overlapping unavailability period is a failure naming it', async () => {
    const when = period(8)
    const saved = await venueRequest('POST', `/venues/${hall.venueId}/unavailability`, 'VS-01', {
      ...when,
      reason: 'maintenance',
      note: 'SPM-62 AC4',
    })
    expect(saved.status, JSON.stringify(saved.body)).toBe(201)
    try {
      const result = await check(await eventOn(8), hall)

      expect(result.verdict).toBe('not suitable')
      const [failure] = result.reasons.filter((reason) => reason.check === 'unavailable')
      expect(failure.severity).toBe('failure')
      expect(failure.message).toMatch(/^This venue is unavailable from .+ \(maintenance\)\.$/)
    } finally {
      await venueRequest('DELETE', `/venues/${hall.venueId}/unavailability/${saved.body.unavailabilityId}`, 'VS-01')
    }
  })

  test('TC-SPM62-AC05 a time outside opening hours is a failure', async () => {
    const base = period(9)
    const result = await check(await eventOn(9), boardroom, { layout: 'Boardroom', expectedAttendance: 10, ...slot(base, -480, -420) })

    expect(result.verdict).toBe('not suitable')
    expect(messages(result, 'failure')).toEqual([
      expect.stringMatching(/^On .+ the event runs 02:00 AM to 03:00 AM UTC, outside this venue's opening hours of 08:00 to 18:00 UTC\.$/),
    ])
  })

  test('TC-SPM62-AC06 attendance above about ninety percent of capacity is a warning', async () => {
    const result = await check(await eventOn(10), boardroom, { expectedAttendance: 19, layout: 'Boardroom' })

    expect(result.verdict).toBe('suitable with warnings')
    expect(messages(result, 'warning')).toEqual([
      'Expected attendance of 19 is above 90% of what this venue can hold in the Boardroom layout (20 people), ' +
        'so it will be a tight fit.',
    ])
  })

  test('TC-SPM62-AC07 an overlapping pending request is a warning', async () => {
    const waiting = await eventOn(11)
    expect((await requestVenue(waiting, hall.venueId, period(11))).status).toBe(201)

    const result = await check(await eventOn(11), hall)

    expect(result.verdict).toBe('suitable with warnings')
    const [warning] = result.reasons.filter((reason) => reason.check === 'pendingRequest')
    expect(warning.severity).toBe('warning')
    expect(warning.message).toContain(`Another booking request for this venue ("${waiting.eventName}")`)
  })

  test('TC-SPM62-AC08 a suitable venue can be requested straight away', async ({ page }) => {
    const event = await eventOn(12)
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    await page.getByTestId(`venue-select-${hall.venueId}`).click()

    await expect(page.getByTestId('suitability-verdict')).toHaveText(/^\s*suitable\s*$/i)
    await expect(page.getByText('This venue meets every requirement for this event.')).toBeVisible()
    await expect(page.getByRole('checkbox', { name: /I have read the warnings above/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Request this venue' })).toBeEnabled()
  })

  test('TC-SPM62-AC08 a venue with only warnings can still be requested', async ({ page }) => {
    // 280 people in the hall's Theatre (300) is above 90%: a warning only. The
    // coordinator ticks that they read the warnings, then may go ahead (SPM-63 AC4).
    const tight = await eventOn(13, { expectedAttendance: 280 })
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${tight.eventId}/venues`)
    await page.getByTestId(`venue-select-${hall.venueId}`).click()
    await expect(page.getByTestId('suitability-verdict')).toHaveText(/suitable with warnings/i)
    await expect(page.getByTestId('suitability-reasons')).toContainText('Warning')
    await expect(page.getByTestId('suitability-reasons')).toContainText('above 90%')
    const send = page.getByRole('button', { name: 'Request this venue' })
    await expect(send).toBeDisabled()

    await page.getByRole('checkbox', { name: /I have read the warnings above/ }).check()

    await expect(send).toBeEnabled()
  })

  test('TC-SPM62-AC08 a venue that fails cannot be requested and the page says why', async ({ page }) => {
    // A Theatre event at a room that only offers a Boardroom.
    const event = await eventOn(14)
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    await page.getByTestId(`venue-select-${boardroom.venueId}`).click()

    await expect(page.getByTestId('suitability-verdict')).toHaveText(/not suitable/i)
    await expect(page.getByTestId('suitability-reasons')).toContainText(
      'This venue does not offer the Theatre layout. Layouts offered: Boardroom.',
    )
    await expect(page.getByRole('button', { name: 'Request this venue' })).toBeDisabled()
  })

  test('TC-SPM62-AC08 the verdict shown is for the venue just selected, even if an earlier check is slow', async ({
    page,
  }) => {
    const event = await eventOn(15)
    await login(page, account('EC-01'))
    // Delay only the boardroom's check (a double for a slow network), so its answer
    // arrives after the hall's.
    await page.route('**/venues/suitability', async (route) => {
      if (route.request().postDataJSON().venueId === boardroom.venueId) {
        await new Promise((done) => setTimeout(done, 2000))
      }
      await route.continue()
    })
    await page.goto(`/app/events/${event.eventId}/venues`)
    const slowAnswer = page.waitForResponse(
      (response) =>
        response.url().includes('/venues/suitability') &&
        response.request().postDataJSON().venueId === boardroom.venueId,
    )

    await page.getByTestId(`venue-select-${boardroom.venueId}`).click()
    await page.getByTestId(`venue-select-${hall.venueId}`).click()
    await slowAnswer // wait for the condition (the late answer has arrived), not a fixed time

    await expect(page.getByRole('heading', { name: hall.name })).toBeVisible()
    await expect(page.getByTestId('suitability-verdict')).toHaveText(/^\s*suitable\s*$/i)
  })

  test('TC-SPM62-AC09 after a search, each venue shows the verdict the check gives when it is picked', async ({
    page,
  }) => {
    // 280 people in the hall's Theatre (300) is a tight fit, so the hall is listed with a warning.
    const tight = await eventOn(16, { expectedAttendance: 280 })
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${tight.eventId}/venues`)
    await page.getByRole('button', { name: 'Search venues' }).click()
    await expect(page.getByTestId('venue-search-summary')).toBeVisible()

    const listed = page.getByTestId(`venue-verdict-${hall.venueId}`)
    await expect(listed).toHaveText(/suitable with warnings/i)
    await page.getByTestId(`venue-select-${hall.venueId}`).click()
    // Both are styled in capitals, so compare the text itself, not how it is drawn.
    await expect(page.getByTestId('suitability-verdict')).toHaveText((await listed.textContent()).trim())
  })

  test('TC-SPM62-AC09 search, booking, and re-verification use the same suitability rule', async () => {
    const event = await eventOn(17, { expectedAttendance: 280 })
    const direct = await check(event, hall)
    const search = await venueRequest('GET', `/venues/search?eventId=${event.eventId}`, 'EC-01')

    expect(search.status).toBe(200)
    const fromSearch = search.body.find((row) => row.venueId === hall.venueId)
    expect([fromSearch.verdict, direct.verdict]).toEqual(['suitable with warnings', 'suitable with warnings'])
  })

  test('TC-SPM62-AC09b re-checking a confirmed booking at new times gives the same verdict as the check', async () => {
    // SPM-86 re-checks a confirmed booking at proposed new times without moving it.
    const confirm = async (event, when) => {
      const sent = await requestVenue(event, hall.venueId, when)
      expect(sent.status, JSON.stringify(sent.body)).toBe(201)
      const approved = await venueRequest('POST', `/venues/bookings/${sent.body.bookingId}/approve`, 'VS-01', {})
      expect(approved.status, JSON.stringify(approved.body)).toBe(200)
      return approved.body
    }
    const event = await eventOn(18)
    const booking = await confirm(event, period(18))
    await confirm(await eventOn(19), period(19)) // another event already holds the hall on day 19
    const recheck = (when) =>
      venueRequest('POST', `/venues/bookings/${booking.bookingId}/recheck`, 'EC-01', {
        proposedStartAt: when.startsAt,
        proposedEndAt: when.endsAt,
      })

    for (const [day, verdict] of [[19, 'not suitable'], [20, 'suitable']]) {
      const rechecked = await recheck(period(day))
      const direct = await check(event, hall, period(day))
      expect(rechecked.status, JSON.stringify(rechecked.body)).toBe(200)
      expect([rechecked.body.verdict, direct.verdict, rechecked.body.conflict]).toEqual([
        verdict,
        verdict,
        verdict === 'not suitable',
      ])
    }
    const unmoved = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect([unmoved.body.status, unmoved.body.startsAt]).toEqual(['approved', booking.startsAt])
  })
})
