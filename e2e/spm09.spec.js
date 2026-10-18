import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { venuePeriod, venueUnavailabilityPayload } from './support/api-data.js'
import { notificationRequest, venueRequest } from './support/venue.js'
import { THEATRE_EVENT, approvedEvent, requestVenue } from './support/venue-request.js'

// A booking can only be requested for an event in planning (SPM-63), and v2/v4
// are closed on Sunday. Pick a day those venues are open, far enough ahead that
// an earlier run's booking is unlikely to still be sitting on it.
function openPeriod(hours, { saturday = true } = {}) {
  let days = 800 + Math.floor(Math.random() * 20000)
  for (let step = 0; step < 7; step += 1) {
    const day = new Date(Date.now() + days * 24 * 60 * 60 * 1000).getUTCDay()
    const closed = day === 0 || (!saturday && day === 6)
    if (!closed) break
    days += 1
  }
  return venuePeriod(days, hours)
}

test.describe('SPM-09 Mark a Venue as Unavailable', () => {
  test('TC-SPM09-AC01 record an unavailability period with end after start', async () => {
    const created = await venueRequest(
      'POST',
      '/venues/v2/unavailability',
      'VS-01',
      venueUnavailabilityPayload(220),
    )
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    expect(new Date(created.body.endsAt).getTime()).toBeGreaterThan(
      new Date(created.body.startsAt).getTime(),
    )

    const inverted = venuePeriod(221, 2)
    const rejected = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: inverted.endsAt,
      endsAt: inverted.startsAt,
      reason: 'maintenance',
    })
    expect([400, 422]).toContain(rejected.status)
  })

  test('TC-SPM09-AC02 a reason from the published list is mandatory', async () => {
    const window = venuePeriod(222, 2)
    const missing = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
    })
    expect([400, 422]).toContain(missing.status)

    const allowed = ['maintenance', 'renovation', 'safety issue', 'internal activity', 'other']
    const created = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'renovation',
      note: 'Optional note',
    })
    expect(created.status).toBe(201)
    expect(allowed).toContain(created.body.reason)
    expect(created.body.note).toBe('Optional note')
  })

  test('TC-SPM09-AC03 an active block excludes the venue from search for that period', async () => {
    const window = venuePeriod(223, 3)
    const block = await venueRequest('POST', '/venues/v4/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'maintenance',
    })
    expect(block.status).toBe(201)

    const search = await venueRequest(
      'GET',
      `/venues/search?startsAt=${encodeURIComponent(window.startsAt)}&endsAt=${encodeURIComponent(window.endsAt)}`,
      'EC-01',
    )
    expect(search.status).toBe(200)
    const ids = (search.body || []).map((row) => row.venueId || row.venue?.venueId)
    expect(ids).not.toContain('v4')
  })

  test('TC-SPM09-AC04 an active block prevents overlapping approval', async () => {
    const event = await approvedEvent(THEATRE_EVENT)
    const window = openPeriod(3)
    const created = await requestVenue(event, 'v3', window)
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    const block = await venueRequest('POST', '/venues/v3/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'safety issue',
    })
    expect(block.status, JSON.stringify(block.body)).toBe(201)
    const approved = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/approve`, 'VS-01', {
      reason: 'blocked',
    })
    expect(approved.status).toBe(409)
  })

  test('TC-SPM09-AC05 the block appears on the calendar as Unavailable', async ({ page }) => {
    const window = venuePeriod(225, 3)
    const block = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'internal activity',
    })
    expect(block.status).toBe(201)
    await login(page, account('VS-01'))
    await page.goto(`/app/venues/v2/calendar`)
    const entry = page.getByTestId(`calendar-unavailable-${block.body.unavailabilityId}`)
    await expect(entry).toBeVisible()
    await expect(entry).toContainText(/unavailable/i)
    await expect(entry).toHaveAttribute('data-kind', 'unavailable')
    await entry.click()
    const detail = page.locator('.detail-card')
    await expect(detail.getByRole('button', { name: 'Edit' })).toBeVisible()
    await expect(detail.getByRole('button', { name: 'Cancel block' })).toBeVisible()
  })

  test('TC-SPM09-AC06 overlapping bookings require acknowledgement and notify coordinators', async () => {
    const event = await approvedEvent({ layoutPreference: 'Classroom', expectedAttendance: 40 })
    const window = openPeriod(3)
    const created = await requestVenue(event, 'v2', window)
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    const approved = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/approve`, 'VS-01', {
      reason: 'seed conflict',
    })
    expect(approved.status, JSON.stringify(approved.body)).toBe(200)
    const blocked = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'maintenance',
    })
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(new RegExp(event.eventId, 'i'))

    const saved = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'maintenance',
      acknowledgeConflicts: true,
    })
    expect(saved.status).toBe(201)

    const notes = await notificationRequest('/notifications?userId=u2', 'EC-01')
    expect(notes.status).toBe(200)
    expect(JSON.stringify(notes.body)).toMatch(/unavailab|maintenance|v2/i)
  })

  test('TC-SPM09-AC07 cancelling a block frees the slot', async () => {
    const event = await approvedEvent({ layoutPreference: 'Boardroom', expectedAttendance: 10 })
    const window = openPeriod(3, { saturday: false })
    const block = await venueRequest('POST', '/venues/v4/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'maintenance',
    })
    expect(block.status).toBe(201)
    const cancelled = await venueRequest(
      'DELETE',
      `/venues/v4/unavailability/${block.body.unavailabilityId}`,
      'VS-01',
    )
    expect([200, 204]).toContain(cancelled.status)

    const created = await requestVenue(event, 'v4', window)
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    const approved = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/approve`, 'VS-01', {
      reason: 'slot free',
    })
    expect(approved.status).toBe(200)
  })

  test('TC-SPM09-AC08 create, change, and cancel are written to the activity log', async () => {
    const window = venuePeriod(228, 3)
    const block = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: window.startsAt,
      endsAt: window.endsAt,
      reason: 'other',
      note: 'log me',
    })
    expect(block.status).toBe(201)
    const updated = await venueRequest(
      'PATCH',
      `/venues/v2/unavailability/${block.body.unavailabilityId}`,
      'VS-01',
      { note: 'updated note' },
    )
    expect(updated.status).toBe(200)
    await venueRequest('DELETE', `/venues/v2/unavailability/${block.body.unavailabilityId}`, 'VS-01')

    const log = await venueRequest('GET', '/venues/v2/activity-log', 'VS-01')
    expect(log.status).toBe(200)
    const actions = (log.body || []).map((row) => row.action)
    expect(actions.join(' ')).toMatch(/unavailab|created|updated|cancel/i)
  })
})
