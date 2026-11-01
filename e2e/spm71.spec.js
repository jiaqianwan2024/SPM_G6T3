import { test, expect } from '@playwright/test'
import { eventApi } from './support/event.js'
import { venueRequest } from './support/venue.js'
import { bookVenue, confirm, planningEvent, readyToConfirm } from './support/confirmation.js'

const DAY = 86400000

// Each test edits an event of its own. Editing seeded e1, e2 or e3 left them renamed, moved
// or reconsidering for every spec and manual check that came after.
test.describe('SPM-71 Update event information and flag significant changes', () => {
  test('TC-SPM71-AC01 the assigned coordinator can edit name, description, purpose, category, notes, and contact without warning', async () => {
    const event = await planningEvent('SPM71-quiet')
    const updated = await eventApi('PATCH', `/${event.eventId}`, 'EC-01', {
      eventName: event.eventName,
      description: 'AUTO-SPM71 quiet edit',
      purpose: 'Updated purpose',
      category: 'Networking',
      internalNotes: 'Staff only',
      organiserContact: 'organiser@connectsphere.com',
    })
    expect(updated.status).toBe(200)
    expect(updated.body.warning || updated.body.requiresConfirmation).toBeFalsy()
  })

  test('TC-SPM71-AC02 date, time, attendance, layout, accessibility, and equipment are significant fields', async () => {
    const meta = await eventApi('GET', '/significant-fields', 'EC-01')
    expect(meta.status).toBe(200)
    const fields = meta.body.fields || meta.body
    for (const field of [
      'proposedStartAt',
      'proposedEndAt',
      'expectedAttendance',
      'layoutPreference',
      'accessibilityNeeds',
      'equipmentRequirements',
    ]) {
      expect(fields).toEqual(expect.arrayContaining([field]))
    }
  })

  test('TC-SPM71-AC03 a significant edit on an event with a confirmed booking requires confirmation and names affected arrangements', async () => {
    const event = await planningEvent('SPM71-significant')
    await bookVenue(event)
    const blocked = await eventApi('PATCH', `/${event.eventId}`, 'EC-01', {
      expectedAttendance: 60,
    })
    expect(blocked.status).toBe(409)
    expect(JSON.stringify(blocked.body)).toMatch(/venue|equipment|re-verif|confirm/i)

    const saved = await eventApi('PATCH', `/${event.eventId}`, 'EC-01', {
      expectedAttendance: 60,
      confirmSignificantChange: true,
    })
    expect(saved.status).toBe(200)
  })

  test('TC-SPM71-AC04 saving a significant change marks affected bookings and reservations for re-verification', async () => {
    const event = await planningEvent('SPM71-reverify')
    const booking = await bookVenue(event)
    const moved = await eventApi('PATCH', `/${event.eventId}`, 'EC-01', {
      proposedStartAt: new Date(Date.parse(event.period.startsAt) + DAY).toISOString(),
      proposedEndAt: new Date(Date.parse(event.period.endsAt) + DAY).toISOString(),
      confirmSignificantChange: true,
    })
    expect(moved.status, JSON.stringify(moved.body)).toBe(200)
    const flagged = await venueRequest('GET', `/venues/bookings/${booking.bookingId}`, 'VS-01')
    expect(flagged.status).toBe(200)
    expect(flagged.body.needsReverification).toBe(true)
  })

  test('TC-SPM71-AC05 every edit is written to the activity log with old and new values', async () => {
    const event = await planningEvent('SPM71-log')
    await eventApi('PATCH', `/${event.eventId}`, 'EC-01', { description: `AUTO-log-${Date.now()}` })
    const log = await eventApi('GET', `/${event.eventId}/activity-log`, 'EC-01')
    expect(log.status).toBe(200)
    expect(JSON.stringify(log.body)).toMatch(/description/)
    expect(JSON.stringify(log.body)).toMatch(/old|previous/)
  })

  test('TC-SPM71-AC06 a significant change on a confirmed event no longer reads as fully confirmed', async () => {
    const event = await readyToConfirm('SPM71-confirmed')
    const confirmed = await confirm(event)
    expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)
    await eventApi('PATCH', `/${event.eventId}`, 'EC-01', {
      expectedAttendance: 60,
      confirmSignificantChange: true,
    })
    const stored = await eventApi('GET', `/${event.eventId}`, 'EO-01')
    expect(stored.body.status).not.toMatch(/^confirmed$/i)
    expect(stored.body.status).toMatch(/reconsider|planning|under review|arrangements/i)
  })

  test('TC-SPM71-AC07 completed, cancelled, or rejected events cannot be edited', async () => {
    const denied = await eventApi('PATCH', '/e8', 'EC-01', { description: 'nope' })
    expect([400, 403, 409]).toContain(denied.status)
  })
})
