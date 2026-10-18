import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'
import {
  createSuiteVenue,
  period,
  retireSuiteVenue,
  shift,
  soonExpiry,
  waitForHoldToExpire,
} from './support/venue-suite.js'

// The suite makes three venues of its own, each in a location no other venue has,
// and retires them afterwards. All times are UTC.
// - hall: Theatre for 300, Stage and PA system, wheelchair accessible and accessible
//   restrooms, open every day 08:00 to 22:00, 30 minutes setup and 60 turnaround, so
//   a 10:00 to 12:00 search occupies it from 09:30 to 13:00.
// - expo: Theatre for 350, a loading dock but no stage, accessible restrooms.
// - boardroom: Boardroom for 20, open every day 08:00 to 18:00.
// Searches return every venue; each check looks only at these three.

const STAMP = Date.now()
const HOURS_8_TO_22 = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => ({ day, opens: '08:00', closes: '22:00' }))
let hall
let expo
let boardroom

function query(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    for (const item of [].concat(value)) search.append(key, item)
  }
  return `?${search}`
}

async function search(params = {}) {
  const response = await venueRequest('GET', `/venues/search${query(params)}`, 'EC-01')
  expect(response.status, JSON.stringify(response.body)).toBe(200)
  return response.body
}

// The suite's own venues among the results, by name.
async function found(params) {
  const rows = await search(params)
  return [hall, expo, boardroom].filter((venue) => rows.some((row) => row.venueId === venue.venueId)).map((v) => v.name)
}

// An event approved for planning on `day`, 10:00 to 12:00.
function eventOn(day, values = {}) {
  const { startsAt, endsAt } = period(day)
  return approvedEvent({ ...THEATRE_EVENT, ...values, proposedStartAt: startsAt, proposedEndAt: endsAt })
}

// A confirmed booking: requested by the assigned coordinator, approved by Venue Staff.
async function confirmedBooking(venue, when) {
  const sent = await requestVenue(await approvedEvent(THEATRE_EVENT), venue.venueId, when)
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  const approved = await venueRequest('POST', `/venues/bookings/${sent.body.bookingId}/approve`, 'VS-01', {})
  expect(approved.status, JSON.stringify(approved.body)).toBe(200)
}

// SPM-9: Venue Staff record an unavailability block; tests remove theirs afterwards.
async function block(venue, startsAt, endsAt) {
  const saved = await venueRequest('POST', `/venues/${venue.venueId}/unavailability`, 'VS-01', {
    startsAt,
    endsAt,
    reason: 'maintenance',
  })
  expect(saved.status, JSON.stringify(saved.body)).toBe(201)
  return saved.body
}

function unblock(venue, saved) {
  return venueRequest('DELETE', `/venues/${venue.venueId}/unavailability/${saved.unavailabilityId}`, 'VS-01')
}

// SPM-116: Venue Staff hold another event's pending request.
async function heldRequest(venue, when, expiresAt) {
  const sent = await requestVenue(await approvedEvent(THEATRE_EVENT), venue.venueId, when)
  expect(sent.status, JSON.stringify(sent.body)).toBe(201)
  const held = await venueRequest('POST', `/venues/bookings/${sent.body.bookingId}/hold`, 'VS-01', { expiresAt })
  expect(held.status, JSON.stringify(held.body)).toBe(200)
  return held.body
}

test.describe('SPM-61 Search and filter venues against event requirements', () => {
  test.beforeAll(async () => {
    hall = await createSuiteVenue('SPM61 Hall', {
      location: `SPM61 Harbour ${STAMP}`,
      layouts: [{ name: 'Theatre', capacity: 300 }],
      facilities: ['PA system', 'Stage'],
      accessibility: ['Wheelchair accessible', 'Accessible restrooms nearby'],
      operatingHours: HOURS_8_TO_22,
      setupMinutes: 30,
      turnaroundMinutes: 60,
    })
    expo = await createSuiteVenue('SPM61 Expo', {
      location: `SPM61 Expo ${STAMP}`,
      layouts: [{ name: 'Theatre', capacity: 350 }],
      facilities: ['Loading dock'],
      accessibility: ['Accessible restrooms nearby'],
      operatingHours: HOURS_8_TO_22,
    })
    boardroom = await createSuiteVenue('SPM61 Boardroom', {
      location: `SPM61 Raffles ${STAMP}`,
      layouts: [{ name: 'Boardroom', capacity: 20 }],
      facilities: [],
      accessibility: ['Wheelchair accessible'],
      operatingHours: HOURS_8_TO_22.map((hours) => ({ ...hours, closes: '18:00' })),
    })
  })

  test.afterAll(async () => {
    for (const venue of [hall, expo, boardroom]) await retireSuiteVenue(venue)
  })

  test('TC-SPM61-AC01 search from an event is pre-filled from the event and can be adjusted', async ({ page }) => {
    const event = await eventOn(1)
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)

    await expect(page.getByLabel('Expected attendance')).toHaveValue('50')
    await expect(page.getByLabel('Layout')).toHaveValue('Theatre')
    await expect(page.getByLabel('Starts (UTC)')).toHaveValue(event.proposedStartAt.slice(0, 16))
    await expect(page.getByLabel('Ends (UTC)')).toHaveValue(event.proposedEndAt.slice(0, 16))
    await expect(page.getByRole('checkbox', { name: 'Stage', exact: true })).toBeChecked()

    // 320 people is more than the hall's Theatre holds (300).
    await page.getByLabel('Expected attendance').fill('320')
    await page.getByRole('button', { name: 'Search venues' }).click()

    await expect(page.getByTestId('venue-search-summary')).toBeVisible()
    await expect(page.getByTestId(`venue-select-${hall.venueId}`)).toHaveCount(0)
    await page.getByRole('button', { name: 'Show all venues' }).click()
    await expect(page.getByTestId(`venue-select-${hall.venueId}`)).toBeVisible()
  })

  test('TC-SPM61-AC02 filters cover time, capacity, location, layout, accessibility, and facilities', async () => {
    const when = period(2)

    expect(
      await found({
        ...when,
        minCapacity: 100,
        location: `SPM61 Harbour ${STAMP}`,
        layout: 'Theatre',
        accessibility: 'Wheelchair accessible',
        facility: ['PA system', 'Stage'],
      }),
    ).toEqual([hall.name])
    expect(await found({ location: `SPM61 Raffles ${STAMP}` })).toEqual([boardroom.name])
  })

  test('TC-SPM61-AC03 a confirmed booking excludes the venue, including its setup and turnaround', async () => {
    const when = period(3)
    await confirmedBooking(hall, when)

    expect(await found(when)).not.toContain(hall.name)
    // Starts 30 minutes after the booking ends: the event times do not overlap, but this
    // search's 30 minute setup runs into the booking's 60 minute turnaround.
    expect(await found({ startsAt: shift(when.endsAt, 30), endsAt: shift(when.endsAt, 150) })).not.toContain(hall.name)
    // Starting 90 minutes after leaves exactly turnaround plus setup, so the windows only touch.
    expect(await found({ startsAt: shift(when.endsAt, 90), endsAt: shift(when.endsAt, 210) })).toContain(hall.name)
  })

  test('TC-SPM61-AC03 an unavailability period excludes the venue, including its setup and turnaround', async () => {
    const when = period(4) // a 10:00 to 12:00 search occupies 09:30 to 13:00
    const inTurnaround = await block(hall, shift(when.endsAt, 30), shift(when.endsAt, 60))
    try {
      expect(await found(when)).not.toContain(hall.name)
    } finally {
      await unblock(hall, inTurnaround)
    }
    // A block that starts as the occupied window ends only touches it.
    const touching = await block(hall, shift(when.endsAt, 60), shift(when.endsAt, 90))
    try {
      expect(await found(when)).toContain(hall.name)
    } finally {
      await unblock(hall, touching)
    }
  })

  test('TC-SPM61-AC03 an active tentative hold excludes the venue, including its setup and turnaround', async () => {
    const when = period(5)
    await heldRequest(hall, when, shift(when.startsAt, -24 * 60))

    expect(await found(when)).not.toContain(hall.name)
    // 30 minutes after it ends: this search's setup runs into the held turnaround.
    expect(await found({ startsAt: shift(when.endsAt, 30), endsAt: shift(when.endsAt, 150) })).not.toContain(hall.name)
  })

  test('TC-SPM61-AC04 an expired tentative hold does not exclude the venue', async () => {
    test.slow() // waits for a real hold to expire
    const when = period(6)
    const held = await heldRequest(hall, when, soonExpiry())
    expect(await found(when)).not.toContain(hall.name)

    await waitForHoldToExpire(held.bookingId)

    expect(await found(when)).toContain(hall.name)
  })

  test('TC-SPM61-AC05 an unsupported layout or too little capacity in that layout excludes the venue', async () => {
    expect(await found({ layout: 'Boardroom', minCapacity: 20 })).toEqual([boardroom.name])
    expect(await found({ layout: 'Boardroom', minCapacity: 21 })).toEqual([])
  })

  test('TC-SPM61-AC06 a missing facility or accessibility feature excludes the venue', async () => {
    expect(await found({ facility: 'Loading dock' })).toEqual([expo.name])
    expect(await found({ accessibility: 'Accessible restrooms nearby' })).toEqual([hall.name, expo.name])
  })

  test('TC-SPM61-AC07 a time outside the opening hours excludes the venue', async () => {
    const when = period(7)
    // 19:00 to 20:00: the hall is open until 22:00, the boardroom closes at 18:00.
    const evening = await found({ startsAt: shift(when.startsAt, 540), endsAt: shift(when.startsAt, 600) })

    expect(evening).toContain(hall.name)
    expect(evening).not.toContain(boardroom.name)
  })

  test('TC-SPM61-AC08 each result shows its capacity in the layout and the headroom', async ({ page }) => {
    const rows = await search({ layout: 'Theatre', minCapacity: 250 })
    expect(rows.find((row) => row.venueId === hall.venueId)).toMatchObject({
      layout: 'Theatre',
      layoutCapacity: 300,
      headroom: 50,
    })

    const event = await eventOn(8)
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${event.eventId}/venues`)
    await page.getByRole('button', { name: 'Search venues' }).click()
    await expect(page.getByTestId(`venue-select-${hall.venueId}`)).toContainText('Capacity 300 in Theatre · 250 spare')
  })

  test('TC-SPM61-AC09 a venue with an overlapping pending request is still shown, marked contested', async ({
    page,
  }) => {
    const event = await eventOn(9)
    const when = { startsAt: event.proposedStartAt, endsAt: event.proposedEndAt }
    const sent = await requestVenue(event, hall.venueId, when)
    expect(sent.status, JSON.stringify(sent.body)).toBe(201)

    const rows = await search(when)
    expect(rows.find((row) => row.venueId === hall.venueId)).toMatchObject({ contested: true })
    // The searching event's own request does not make the venue contested for it.
    const own = await search({ ...when, eventId: event.eventId })
    expect(own.find((row) => row.venueId === hall.venueId)).toMatchObject({ contested: false })

    const other = await eventOn(9)
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${other.eventId}/venues`)
    await page.getByRole('button', { name: 'Search venues' }).click()
    await expect(page.getByTestId(`venue-contested-${hall.venueId}`)).toHaveText(
      "Contested: another event's request for this time is waiting for Venue Staff",
    )
  })
})
