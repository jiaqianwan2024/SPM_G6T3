import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import { createSuiteVenue, openBookingRequests, period, retireSuiteVenue, shift } from './support/venue-suite.js'

// Singapore time (SGT, UTC+8). The server stores and sends UTC; people read and
// type times in Singapore time, and a venue's opening hours are Singapore hours.
// The browser runs as if the computer were in New York, so each screen check
// proves the time shown does not depend on the viewer's own time zone.
// The suite makes its own venues and events, each on its own fixed day, and
// retires the venues afterwards.

test.use({ timezoneId: 'America/New_York' })

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
const HOUR = 60

let hall
let boardroom

// "19 Oct 2026": a time's Singapore date, as the screens write it.
const sgtDate = (iso) =>
  new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Singapore', day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(iso),
  )

// "07 Jan 2030": the same, with a two-digit day, as server messages write it.
const sgtDateInMessage = (iso) => sgtDate(iso).padStart(11, '0')

// The UTC date part ("YYYY-MM-DD") of a time.
const utcDay = (iso) => new Date(iso).toISOString().slice(0, 10)

// The first suite day (from `from`) whose date falls on the given weekday (0 is Sunday).
function dayOn(weekday, from) {
  for (let day = from; day < from + 7; day += 1) {
    if (new Date(period(day).startsAt).getUTCDay() === weekday) return day
  }
  throw new Error('no such day')
}

async function check(event, venue, extras) {
  const result = await venueRequest('POST', '/venues/suitability', 'EC-01', {
    eventId: event.eventId,
    venueId: venue.venueId,
    ...extras,
  })
  expect(result.status, JSON.stringify(result.body)).toBe(200)
  return result.body
}

async function searchFinds(venue, startsAt, endsAt) {
  const query = new URLSearchParams({ startsAt, endsAt })
  const response = await venueRequest('GET', `/venues/search?${query}`, 'EC-01')
  expect(response.status, JSON.stringify(response.body)).toBe(200)
  return response.body.some((row) => row.venueId === venue.venueId)
}

test.describe('Singapore time (SGT)', () => {
  test.beforeAll(async () => {
    hall = await createSuiteVenue('SGT Hall', { layouts: [{ name: 'Theatre', capacity: 300 }] })
    boardroom = await createSuiteVenue('SGT Boardroom', {
      layouts: [{ name: 'Boardroom', capacity: 20 }],
      operatingHours: WEEKDAYS.map((day) => ({ day, opens: '08:00', closes: '18:00' })),
    })
  })

  test.afterAll(async () => {
    for (const venue of [hall, boardroom]) await retireSuiteVenue(venue)
  })

  test('TC-SGT-AC01 a booking is shown in Singapore time on a computer set to another time zone', async ({ page }) => {
    const when = period(1) // 02:00 to 04:00 UTC, which is 10:00 to 12:00 in Singapore
    const sent = await requestVenue(await approvedEvent(THEATRE_EVENT), hall.venueId, when)
    expect(sent.status, JSON.stringify(sent.body)).toBe(201)

    await login(page, account('VS-01'))
    await openBookingRequests(page, hall)

    const card = page.getByTestId(`booking-request-${sent.body.bookingId}`)
    await expect(card.getByTestId('booking-starts-at')).toHaveText(`${sgtDate(when.startsAt)}, 10:00 to 12:00 SGT`)
    await expect(page.getByText('All times are in Singapore time (SGT).')).toBeVisible()
  })

  test('TC-SGT-AC01b the shared time formatter reads server times as UTC and writes Singapore time', async ({ page }) => {
    await page.goto('/')
    const shown = await page.evaluate(async () => {
      const t = await import('/src/utils/datetime.js')
      return {
        plain: t.formatSgt('2026-10-19T02:00:00'),
        withZone: t.formatSgt('2026-10-19T02:00:00Z'),
        pastMidnight: t.formatSgt('2026-10-19T16:00:00'),
        beforeMidnight: t.formatSgt('2026-10-19T15:59:00'),
        sameDayRange: t.formatSgtRange('2026-10-19T02:00:00', '2026-10-19T04:00:00'),
        overnightRange: t.formatSgtRange('2026-10-19T14:00:00', '2026-10-19T17:00:00'),
        day: t.sgtDay('2026-10-19T16:00:00'),
        input: t.toSgtInput('2026-10-19T16:30:00'),
        empty: t.formatSgt(''),
        notATime: t.formatSgt('soon'),
      }
    })

    expect(shown).toEqual({
      plain: '19 Oct 2026, 10:00 SGT',
      withZone: '19 Oct 2026, 10:00 SGT',
      pastMidnight: '20 Oct 2026, 00:00 SGT',
      beforeMidnight: '19 Oct 2026, 23:59 SGT',
      sameDayRange: '19 Oct 2026, 10:00 to 12:00 SGT',
      overnightRange: '19 Oct 2026, 22:00 to 20 Oct 2026, 01:00 SGT',
      day: '2026-10-20',
      input: '2026-10-20T00:30',
      empty: '',
      notATime: '',
    })
  })

  test('TC-SGT-AC02 a time typed into a form is read as Singapore time and saved as UTC', async ({ page }) => {
    // 00:30 to 01:30 Singapore time on a suite day is 16:30 to 17:30 UTC the day before.
    const sgtDay = utcDay(period(3).startsAt)
    const utcBefore = utcDay(shift(period(3).startsAt, -24 * HOUR))

    await login(page, account('VS-01'))
    await page.goto(`/app/venues/${hall.venueId}/calendar`)
    await page.getByTestId('mark-unavailable').click()
    await page.getByLabel('Start (SGT)').fill(`${sgtDay}T00:30`)
    await page.getByLabel('End (SGT)').fill(`${sgtDay}T01:30`)
    const saved = page.waitForResponse(
      (response) => response.url().includes(`/venues/${hall.venueId}/unavailability`) && response.request().method() === 'POST',
    )
    await page.getByRole('button', { name: 'Save block' }).click()
    const block = await (await saved).json()

    try {
      expect([block.startsAt, block.endsAt]).toEqual([`${utcBefore}T16:30:00`, `${utcBefore}T17:30:00`])
      // Opened on its day, the block reads back in Singapore time.
      await page.goto(`/app/venues/${hall.venueId}/calendar?at=${block.startsAt}`)
      await page.getByTestId(`calendar-unavailable-${block.unavailabilityId}`).click()
      await expect(page.getByText(`${sgtDate(`${sgtDay}T00:00:00+08:00`)}, 00:30 SGT`)).toBeVisible()
    } finally {
      await venueRequest('DELETE', `/venues/${hall.venueId}/unavailability/${block.unavailabilityId}`, 'VS-01')
    }
  })

  test('TC-SGT-AC03 opening hours are Singapore hours, in the suitability check and in search alike', async () => {
    const monday = period(dayOn(1, 4)).startsAt.slice(0, 10)
    const event = await approvedEvent({ ...THEATRE_EVENT, layoutPreference: 'Boardroom', expectedAttendance: 10 })
    const at = (time) => `${monday}T${time}:00.000Z`

    // 00:00 to 10:00 UTC is exactly 08:00 to 18:00 in Singapore: inside (boundary).
    const inside = await check(event, boardroom, { startsAt: at('00:00'), endsAt: at('10:00') })
    // 10:00 to 11:00 UTC is 06:00 PM to 07:00 PM in Singapore: after closing.
    const after = await check(event, boardroom, { startsAt: at('10:00'), endsAt: at('11:00') })

    expect(inside.verdict).toBe('suitable')
    expect(after.verdict).toBe('not suitable')
    expect(after.reasons.map((reason) => reason.message)).toEqual([
      expect.stringMatching(/^On Monday .+ the event runs 06:00 PM to 07:00 PM SGT, outside this venue's opening hours of 08:00 to 18:00 SGT\.$/),
    ])
    expect(await searchFinds(boardroom, at('00:00'), at('10:00'))).toBe(true)
    expect(await searchFinds(boardroom, at('10:00'), at('11:00'))).toBe(false)
  })

  test('TC-SGT-AC03b the day is the Singapore day: Friday evening UTC is Saturday in Singapore', async () => {
    const friday = period(dayOn(5, 4)).startsAt.slice(0, 10)
    const event = await approvedEvent({ ...THEATRE_EVENT, layoutPreference: 'Boardroom', expectedAttendance: 10 })

    // 20:00 to 21:00 UTC on Friday is 04:00 to 05:00 on Saturday in Singapore.
    const result = await check(event, boardroom, { startsAt: `${friday}T20:00:00.000Z`, endsAt: `${friday}T21:00:00.000Z` })

    expect(result.reasons.map((reason) => reason.message)).toEqual([
      expect.stringMatching(/^This venue is closed on Saturday .+, so the event is outside its opening hours\.$/),
    ])
  })

  test('TC-SGT-AC04 a time inside a message is written in Singapore time', async () => {
    const venue = await createSuiteVenue('SGT Retire Hall', { layouts: [{ name: 'Theatre', capacity: 300 }] })
    try {
      const when = period(2)
      const sent = await requestVenue(await approvedEvent(THEATRE_EVENT), venue.venueId, when)
      expect(sent.status, JSON.stringify(sent.body)).toBe(201)
      const approved = await venueRequest('POST', `/venues/bookings/${sent.body.bookingId}/approve`, 'VS-01', {})
      expect(approved.status, JSON.stringify(approved.body)).toBe(200)

      const blocked = await venueRequest('POST', `/venues/${venue.venueId}/retire`, 'VS-01')

      expect(blocked.status).toBe(409)
      expect(blocked.body.detail).toBe(
        `This venue has 1 confirmed upcoming booking that would be affected: event ${sent.body.eventId}, ` +
          `starting ${sgtDateInMessage(when.startsAt)}, 10:00 AM SGT.`,
      )
    } finally {
      await retireSuiteVenue(venue)
    }
  })

  test('TC-SGT-AC05 the API still stores and returns UTC', async () => {
    const when = period(5)
    const sent = await requestVenue(await approvedEvent(THEATRE_EVENT), hall.venueId, when)
    expect(sent.status, JSON.stringify(sent.body)).toBe(201)

    const stored = await venueRequest('GET', `/venues/bookings/${sent.body.bookingId}`, 'VS-01')

    expect([stored.body.startsAt, stored.body.endsAt]).toEqual([when.startsAt.slice(0, 19), when.endsAt.slice(0, 19)])
    expect(stored.body.startsAt.endsWith('T02:00:00')).toBe(true)
  })
})
