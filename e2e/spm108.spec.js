import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venuePeriod, venueUnavailabilityPayload } from './support/api-data.js'
import { releaseBooking, venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'

// A random day years ahead, as freshPeriod picks, so a rerun rarely meets an earlier run's booking.
function farDay() {
  return 300 + Math.floor(Math.random() * 30000)
}

test.describe('SPM-108 Venue availability calendar', () => {
  test('TC-SPM108-AC01 the calendar shows confirmed bookings, pending requests, and unavailability', async () => {
    // Each booking is for its own Theatre event approved for planning, on v3 (Exhibition Hall B), on random
    // days far ahead, so neither seeded events' states nor an earlier run's bookings get in the way.
    const day = farDay()
    const pendingEvent = await approvedEvent(THEATRE_EVENT)
    const confirmedEvent = await approvedEvent(THEATRE_EVENT)
    const pending = await requestVenue(pendingEvent, 'v3', venuePeriod(day))
    const confirmed = await requestVenue(confirmedEvent, 'v3', venuePeriod(day + 1))
    const block = await venueRequest('POST', '/venues/v3/unavailability', 'VS-01', venueUnavailabilityPayload(day + 2))
    try {
      expect([pending.status, confirmed.status, block.status]).toEqual([201, 201, 201])
      const approved = await venueRequest('POST', `/venues/bookings/${confirmed.body.bookingId}/approve`, 'VS-01', {
        reason: 'calendar confirmed',
      })
      expect(approved.status, JSON.stringify(approved.body)).toBe(200)

      const range = `from=${encodeURIComponent(venuePeriod(day - 1).startsAt)}&to=${encodeURIComponent(venuePeriod(day + 3).endsAt)}`
      const calendar = await venueRequest('GET', `/venues/v3/calendar?${range}`, 'VS-01')
      expect(calendar.status).toBe(200)
      const byId = Object.fromEntries(calendar.body.entries.map((entry) => [entry.id, entry]))
      expect(byId[pending.body.bookingId].kind).toBe('pending')
      expect(byId[pending.body.bookingId].eventName).toBe(pendingEvent.eventName)
      expect(byId[confirmed.body.bookingId].kind).toBe('confirmed')
      expect(byId[block.body.unavailabilityId].kind).toBe('unavailable')
    } finally {
      await releaseBooking(pending.body.bookingId)
      await releaseBooking(confirmed.body.bookingId)
      await venueRequest('DELETE', `/venues/v3/unavailability/${block.body.unavailabilityId}`, 'VS-01')
    }
  })

  test('TC-SPM108-AC02 each entry kind is visually distinct', async ({ page }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v1/calendar')
    await expect(page.getByTestId('calendar-kind-confirmed').first()).toBeVisible()
    await expect(page.getByTestId('calendar-kind-pending').first()).toBeVisible()
    const confirmedClass = await page.getByTestId('calendar-kind-confirmed').first().getAttribute('data-kind')
    const pendingClass = await page.getByTestId('calendar-kind-pending').first().getAttribute('data-kind')
    expect(confirmedClass).not.toBe(pendingClass)
  })

  test('TC-SPM108-AC03 an entry shows event name, organisation, and time, and opens the record', async ({
    page,
  }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v1/calendar')
    const entry = page.getByTestId('calendar-booking-vb-soon')
    await expect(entry).toBeVisible()
    await expect(entry).toContainText(/AI in Events Summit/)
    await expect(entry).toContainText(/Apex Partners/)
    await entry.click()
    await expect(page).toHaveURL(/e1|booking|vb-soon/i)
  })

  test('TC-SPM108-AC04 times outside opening hours are shown as unavailable', async ({ page }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v4/calendar')
    await expect(page.getByTestId('calendar-outside-hours').first()).toBeVisible()
  })

  test('TC-SPM108-AC05 the calendar can be viewed by week and month, including past dates', async ({
    page,
  }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v1/calendar')
    await page.getByTestId('calendar-view-week').click()
    await expect(page.getByTestId('venue-calendar')).toHaveAttribute('data-view', 'week')
    await page.getByTestId('calendar-view-month').click()
    await expect(page.getByTestId('venue-calendar')).toHaveAttribute('data-view', 'month')
    await page.getByTestId('calendar-prev').click()
    await expect(page.getByTestId('venue-calendar')).toBeVisible()
  })

  test('TC-SPM108-AC06 a new decision appears the next time the calendar is opened', async ({ page }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    const request = await requestVenue(event, 'v3', venuePeriod(farDay()))
    expect(request.status, JSON.stringify(request.body)).toBe(201)
    const created = request.body
    // The calendar opens on today; the booking is far ahead, so open it on the booking's date.
    const calendar = `/app/venues/v3/calendar?at=${encodeURIComponent(created.startsAt)}`
    try {
      await login(page, account('VS-01'))
      await page.goto(calendar)
      await expect(page.getByTestId(`calendar-booking-${created.bookingId}`)).toHaveAttribute('data-kind', 'pending')
      await venueRequest('POST', `/venues/bookings/${created.bookingId}/approve`, 'VS-01', {
        reason: 'refresh',
      })
      await page.goto(calendar)
      await expect(page.getByTestId(`calendar-booking-${created.bookingId}`)).toHaveAttribute(
        'data-kind',
        /confirmed|approved/,
      )
    } finally {
      await releaseBooking(created.bookingId)
    }
  })

  test('TC-SPM108-AC07 internal roles can read any venue calendar', async () => {
    for (const id of ['EC-01', 'VS-01', 'TS-01']) {
      const calendar = await venueRequest('GET', '/venues/v1/calendar', id)
      expect(calendar.status, id).toBe(200)
    }
    const denied = await venueRequest('GET', '/venues/v1/calendar', 'ATT-01')
    expect(denied.status).toBe(403)
  })

  test('TC-SPM108-AC08 a range with nothing booked shows an empty calendar, not an error', async ({
    page,
  }) => {
    const far = venuePeriod(400, 2)
    const calendar = await venueRequest(
      'GET',
      `/venues/v4/calendar?from=${encodeURIComponent(far.startsAt)}&to=${encodeURIComponent(far.endsAt)}`,
      'VS-01',
    )
    expect(calendar.status).toBe(200)
    expect(calendar.body.error).toBeFalsy()

    await login(page, account('VS-01'))
    await page.goto('/app/venues/v4/calendar?from=2099-01-01&to=2099-01-07')
    await expect(page.getByTestId('venue-calendar-empty')).toBeVisible()
  })
})
