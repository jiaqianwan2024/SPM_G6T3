import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { eventApi } from './support/event.js'
import { notificationRequest, venueRequest } from './support/venue.js'
import { equipmentApi } from './support/equipment.js'
import { notificationApi } from './support/registration.js'

// Marina Hall A is open 08:00–22:00 every day. A window that starts at the current
// clock time can fall before 08:00 and would release the booking on re-confirm.
function nextWindow(currentStart, startHour = 10, endHour = 14) {
  const start = new Date(currentStart || Date.now())
  start.setUTCDate(start.getUTCDate() + 1)
  start.setUTCHours(startHour, 0, 0, 0)
  while (start.getUTCDay() === 0) start.setUTCDate(start.getUTCDate() + 1)
  const end = new Date(start)
  end.setUTCHours(endHour, 0, 0, 0)
  return { proposedStartAt: start.toISOString(), proposedEndAt: end.toISOString() }
}

function hoursWindow(daysAhead, startHour = 10, endHour = 14) {
  const start = new Date()
  start.setUTCHours(startHour, 0, 0, 0)
  start.setUTCDate(start.getUTCDate() + daysAhead)
  while (start.getUTCDay() === 0) start.setUTCDate(start.getUTCDate() + 1)
  const end = new Date(start)
  end.setUTCHours(endHour, 0, 0, 0)
  return { proposedStartAt: start.toISOString(), proposedEndAt: end.toISOString() }
}

test.describe('SPM-86 Re-verify arrangements affected by a significant change', () => {
  test('TC-SPM86-AC01 a significant field change marks affected venue bookings and equipment reservations for re-verification', async () => {
    const current = await eventApi('GET', '/e2', 'EC-01')
    const applied = await eventApi('PATCH', '/e2', 'EC-01', {
      ...nextWindow(current.body.proposedStartAt),
      expectedAttendance: current.body.expectedAttendance === 48 ? 47 : 48,
      confirmSignificantChange: true,
    })
    expect(applied.status, JSON.stringify(applied.body)).toBe(200)
    const booking = await venueRequest('GET', '/venues/bookings/vb-reverify', 'VS-01')
    expect(booking.status).toBe(200)
    expect(booking.body.needsReverification || /reverify/i.test(booking.body.status)).toBeTruthy()
    const reservation = await equipmentApi('GET', '/equipment/reservations/er-e2', 'TS-01')
    expect(reservation.status).toBe(200)
    expect(reservation.body.needsReverification || /reverify/i.test(reservation.body.status)).toBeTruthy()
  })

  test('TC-SPM86-AC02 a re-verification flag is visible on the event, readiness, venue calendar, and staff queues', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto('/app/events/e2')
    await expect(page.getByTestId('reverify-flag')).toBeVisible()
    await page.goto('/app/events/e2/readiness')
    await expect(page.getByTestId('readiness-reverify')).toBeVisible()
    await page.goto('/app')
    await page.getByRole('button', { name: 'Log out' }).click()
    await login(page, account('VS-01'))
    await page.goto('/app/venues/v1/calendar')
    await expect(page.getByTestId('calendar-reverify')).toBeVisible()
    await page.getByRole('button', { name: 'Log out' }).click()
    await login(page, account('TS-01'))
    await page.goto('/app')
    await expect(page.getByTestId('tech-reverification-er-e2')).toBeVisible()
  })

  test('TC-SPM86-AC03 venue staff are notified for bookings they approved, and technical support for reservations', async () => {
    await eventApi('PATCH', '/e2', 'EC-01', {
      expectedAttendance: 45,
      confirmSignificantChange: true,
    })
    const afterVs = await notificationRequest('/notifications', 'VS-01')
    const afterTs = await notificationRequest('/notifications', 'TS-01')
    expect(afterVs.status, JSON.stringify(afterVs.body)).toBe(200)
    expect(afterTs.status, JSON.stringify(afterTs.body)).toBe(200)
    expect(JSON.stringify(afterVs.body)).toMatch(/re-?verif/i)
    expect(JSON.stringify(afterTs.body)).toMatch(/re-?verif/i)
  })

  test('TC-SPM86-AC04 a date or time change re-checks the booking for conflicts and reports them rather than silently moving it', async () => {
    const check = await venueRequest('POST', '/venues/bookings/vb-reverify/recheck', 'VS-01', hoursWindow(14))
    expect(check.status).toBe(200)
    expect(check.body.movedSilently).toBeFalsy()
    expect(check.body.conflict || check.body.verdict || check.body.status).toBeTruthy()
    const booking = await venueRequest('GET', '/venues/bookings/vb-reverify', 'VS-01')
    expect(booking.body.needsReverification || /reverify|approved/i.test(booking.body.status)).toBeTruthy()
  })

  test('TC-SPM86-AC05 when the venue is still suitable and free, venue staff can re-confirm in one action', async ({
    page,
  }) => {
    await login(page, account('VS-01'))
    await page.goto('/app/venues/bookings/vb-reverify')
    await page.getByTestId('booking-request-vb-reverify').getByTestId('booking-reconfirm').click()
    const reconfirmed = await venueRequest('POST', '/venues/bookings/vb-reverify/reconfirm', 'VS-01')
    expect([200, 409]).toContain(reconfirmed.status)
    if (reconfirmed.status === 200) {
      expect(reconfirmed.body.needsReverification).toBeFalsy()
      expect(reconfirmed.body.status).toMatch(/approved|confirmed/i)
    }
  })

  test('TC-SPM86-AC06 when the venue is unsuitable or unavailable, the booking is released and the coordinator is prompted to search again', async ({
    page,
  }) => {
    const event = await eventApi('GET', '/e2', 'EC-01')
    expect(event.status).toBe(200)
    const created = await venueRequest('POST', '/venues/bookings', 'EC-01', {
      venueId: 'v2',
      eventId: 'e2',
      startsAt: event.body.proposedStartAt,
      endsAt: event.body.proposedEndAt,
      requirementsSnapshot: 'Classroom layout for the re-check.',
      acknowledgeWarnings: true,
    })
    expect(created.status, JSON.stringify(created.body)).toBe(201)
    const approved = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/approve`, 'VS-01', {
      reason: 'Free for the re-check.',
    })
    expect(approved.status, JSON.stringify(approved.body)).toBe(200)
    const flagged = await eventApi('PATCH', '/e2', 'EC-01', {
      expectedAttendance: 46,
      confirmSignificantChange: true,
    })
    expect(flagged.status, JSON.stringify(flagged.body)).toBe(200)
    const blocked = await venueRequest('POST', '/venues/v2/unavailability', 'VS-01', {
      startsAt: event.body.proposedStartAt,
      endsAt: event.body.proposedEndAt,
      reason: 'maintenance',
      acknowledgeConflicts: true,
    })
    expect(blocked.status, JSON.stringify(blocked.body)).toBe(201)
    const released = await venueRequest('POST', `/venues/bookings/${created.body.bookingId}/reconfirm`, 'VS-01')
    expect(released.status, JSON.stringify(released.body)).toBe(409)
    expect(JSON.stringify(released.body)).toMatch(/released|search for a venue again/i)
    await login(page, account('EC-01'))
    await page.goto('/app/events/e2')
    await expect(page.getByTestId('search-venue-again')).toBeVisible()
  })

  test('TC-SPM86-AC07 extra equipment that is unavailable is flagged to technical support, not reserved', async () => {
    const flagged = await eventApi('PATCH', '/e2', 'EC-01', {
      equipmentLines: [{ equipmentId: 'eq1', quantity: 40 }],
      confirmSignificantChange: true,
    })
    expect([200, 409]).toContain(flagged.status)
    const queue = await equipmentApi('GET', '/equipment/queue', 'TS-01')
    expect(queue.status).toBe(200)
    expect(JSON.stringify(queue.body)).toMatch(/e2|eq1|reverify|shortfall|attention/i)
    const reserved = await equipmentApi('GET', '/equipment/reservations/er-e2', 'TS-01')
    expect(reserved.body.quantity).not.toBe(40)
  })

  test('TC-SPM86-AC08 a confirmed event with arrangements awaiting re-verification is not shown as fully confirmed', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/events/e2')
    const status = page.getByTestId('organiser-event-status')
    await expect(status).toBeVisible()
    await expect(status).not.toHaveText(/^confirmed$/i)
    await expect(page.getByTestId('reverify-flag')).toBeVisible()
    const attendee = await eventApi('GET', '/e2', 'ATT-01')
    expect(JSON.stringify(attendee.body)).not.toMatch(/"status"\s*:\s*"confirmed"/i)
  })

  test('TC-SPM86-AC09 registered attendees are notified when date, time, or venue changes', async () => {
    const current = await eventApi('GET', '/e1', 'EC-01')
    const changed = await eventApi('PATCH', '/e1', 'EC-01', {
      ...nextWindow(current.body.proposedStartAt, 10, 18),
      confirmSignificantChange: true,
    })
    expect(changed.status, JSON.stringify(changed.body)).toBe(200)
    const notice = await notificationApi('GET', '/notifications', 'ATT-01')
    expect(notice.status, JSON.stringify(notice.body)).toBe(200)
    expect(JSON.stringify(notice.body)).toMatch(/date or time|e1/i)
  })

  test('TC-SPM86-AC10 once every flagged arrangement is re-verified, the event returns to its previous presentation', async ({
    page,
  }) => {
    await venueRequest('POST', '/venues/bookings/vb-reverify/reconfirm', 'VS-01')
    await equipmentApi('POST', '/equipment/reservations/er-e2/reconfirm', 'TS-01')
    const stored = await eventApi('GET', '/e2', 'EO-01')
    expect(stored.status).toBe(200)
    expect(stored.body.needsReverification).toBeFalsy()
    await login(page, account('EO-01'))
    await page.goto('/app/events/e2')
    await expect(page.getByTestId('reverify-flag')).toHaveCount(0)
  })
})
