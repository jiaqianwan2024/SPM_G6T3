import { execFileSync } from 'node:child_process'
import { test, expect } from '@playwright/test'
import { serviceUrls } from './support/api-data.js'
import { bookVenue, confirm, events, passSafetyReview, planningEvent, readyToConfirm, requestBooking } from './support/confirmation.js'
import { assignCoordinator, createSubmittedEvent, eventApi } from './support/event.js'
import { notificationApi } from './support/registration.js'
import { venueRequest } from './support/venue.js'

// SPM-93 is checked through the routes that exist: actions taken through each
// service, the caller's own inbox (GET /notifications), and for the rules the
// notification service applies on every publish (actor, attendee, repeat), its
// service-key publish route, which every other service calls.

const SERVICE_KEY = process.env.INTERNAL_SERVICE_KEY || 'dev-only-service-key'

async function inbox(accountId, eventId) {
  const listed = await notificationApi('GET', '/notifications?pageSize=100', accountId)
  expect(listed.status, JSON.stringify(listed.body)).toBe(200)
  return listed.body.filter((row) => row.eventId === eventId)
}

function types(rows) {
  return rows.map((row) => row.type)
}

async function publish(body) {
  const response = await fetch(`${serviceUrls.notification}/notifications/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Service-Key': SERVICE_KEY },
    body: JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

async function assignedEvent(label) {
  const event = await createSubmittedEvent('EO-01', `AUTO-SPM93-${label}-${Date.now()}`)
  await assignCoordinator(event.eventId, 'u2')
  return event
}

function cancel(event, accountId) {
  return events('POST', `/${event.eventId}/cancel`, accountId, { reason: 'AUTO-SPM93 cancelled' })
}

// An event can only be completed after its end time, and the API refuses past dates,
// so the test moves its own event into the past directly in the database.
function endInThePast(eventId) {
  const sql =
    'UPDATE events SET proposed_start_at = UTC_TIMESTAMP() - INTERVAL 2 HOUR, ' +
    `proposed_end_at = UTC_TIMESTAMP() - INTERVAL 1 HOUR WHERE event_id = '${eventId}'`
  execFileSync(
    'docker',
    ['compose', '-f', 'infra/docker-compose.yml', 'exec', '-T', 'mysql', 'mysql', '-uroot', '-pconnectsphere', 'event', '-e', sql],
    { stdio: 'pipe' },
  )
}

// The cancellation notice is published after the response, as a background task.
async function eventuallyContains(accountId, eventId, type) {
  await expect.poll(async () => types(await inbox(accountId, eventId)), { timeout: 15_000 }).toContain(type)
}

test.describe('SPM-93 Notification delivery and recipient resolution', () => {
  test('TC-SPM93-AC01 one notification service is the only way a notification record is created', async () => {
    const event = await assignedEvent('only')
    // The action happened in event-service; the record is read back from notification-service.
    expect(types(await inbox('EC-01', event.eventId))).toContain('booking.assigned')
    // Event-service has no route of its own that writes a notification.
    const direct = await eventApi('POST', `/${event.eventId}/notifications`, 'EC-01', { message: 'no row' })
    expect([404, 405]).toContain(direct.status)
  })

  test('TC-SPM93-AC02 each notification records recipient, trigger, event, message, link, time, and read state', async () => {
    const event = await assignedEvent('fields')
    const row = (await inbox('EC-01', event.eventId)).find((item) => item.type === 'booking.assigned')
    expect(row, 'booking.assigned row for EC-01').toBeTruthy()
    expect(row).toMatchObject({
      userId: 'u2',
      type: 'booking.assigned',
      eventId: event.eventId,
      resourceType: 'event',
      resourceId: event.eventId,
      link: `/app/events/${event.eventId}`,
      isRead: false,
    })
    expect(`${row.title} ${row.body}`).toContain(event.eventName)
    expect(Number.isNaN(Date.parse(row.createdAt))).toBe(false)
  })

  test('TC-SPM93-AC03 recipients are resolved from their relationship to the event, not from role alone', async () => {
    const event = await createSubmittedEvent('EO-01', `AUTO-SPM93-relations-${Date.now()}`)
    // Submitting tells the Event Coordinator Lead a request is waiting.
    expect(types(await inbox('ECL-01', event.eventId))).toContain('booking.submitted')

    await assignCoordinator(event.eventId, 'u2')
    expect(types(await inbox('EC-01', event.eventId))).toContain('booking.assigned')
    expect(types(await inbox('EO-01', event.eventId))).toContain('event.coordinator')
    // Another coordinator, and an organiser from another organisation, have no tie to the event.
    expect(await inbox('EC-02', event.eventId)).toEqual([])
    expect(await inbox('EO-02', event.eventId)).toEqual([])

    // A reassignment also tells the coordinator it was taken from.
    await assignCoordinator(event.eventId, 'u6')
    expect(types(await inbox('EC-01', event.eventId))).toContain('event.reassigned')
    expect(types(await inbox('EC-02', event.eventId))).toContain('booking.assigned')
  })

  test('TC-SPM93-AC04 the triggers include assignment, reassignment, hold expiry, venue unavailability, and the safety decision', async () => {
    test.setTimeout(180_000)

    // Assignment and reassignment.
    const submitted = await createSubmittedEvent('EO-01', `AUTO-SPM93-assign-${Date.now()}`)
    await assignCoordinator(submitted.eventId, 'u6')
    expect(types(await inbox('EC-02', submitted.eventId))).toContain('booking.assigned')
    await assignCoordinator(submitted.eventId, 'u2')
    expect(types(await inbox('EC-02', submitted.eventId))).toContain('event.reassigned')

    // The Safety Officer's decision.
    const reviewed = await planningEvent('SPM93-safety')
    await bookVenue(reviewed)
    await passSafetyReview(reviewed)
    expect(types(await inbox('EO-01', reviewed.eventId))).toContain('safety.approved')

    // Venue unavailability that affects a confirmed booking.
    const blocked = await venueRequest('POST', '/venues/v1/unavailability', 'VS-01', {
      startsAt: reviewed.period.startsAt,
      endsAt: reviewed.period.endsAt,
      reason: 'maintenance',
      acknowledgeConflicts: true,
    })
    expect(blocked.status, JSON.stringify(blocked.body)).toBe(201)
    expect(types(await inbox('EC-01', reviewed.eventId))).toContain('venue.unavailability')

    // Tentative-hold expiry, announced by the reminder check.
    const held = await planningEvent('SPM93-hold')
    const booking = await requestBooking(held)
    const placed = await venueRequest('POST', `/venues/bookings/${booking.bookingId}/hold`, 'VS-01', {
      expiresAt: new Date(Date.now() + 3000).toISOString(),
    })
    expect(placed.status, JSON.stringify(placed.body)).toBe(200)
    await new Promise((resolve) => setTimeout(resolve, 5000))
    const run = await events('POST', '/reminders/run', 'EC-01')
    expect(run.status, JSON.stringify(run.body)).toBe(200)
    expect(run.body.expiredHolds).toContain(booking.bookingId)
    expect(types(await inbox('EC-01', held.eventId))).toContain('hold.expired')
  })

  // A replacement-venue request emails Venue Staff (a stub that only logs) and stores no
  // notification record, so there is nothing for a test to read. Needs an in-app notice.
  test.fixme('TC-SPM93-AC04b a request for a replacement venue notifies Venue Staff', async () => {})

  test('TC-SPM93-AC05 the user who performed an action is not notified about it', async () => {
    const event = await assignedEvent('actor')
    const cancelled = await cancel(event, 'EC-01')
    expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200)
    // The organiser is told; the coordinator who cancelled is not, though they are a recipient.
    await eventuallyContains('EO-01', event.eventId, 'event.cancelled')
    expect(types(await inbox('EC-01', event.eventId))).not.toContain('event.cancelled')

    // The same rule on the publish route itself.
    const published = await publish({
      trigger: 'booking.assigned',
      occurrenceId: `${event.eventId}:actor-check`,
      eventId: event.eventId,
      actorId: 'u2',
      recipients: [{ userId: 'u2', role: 'coordinator' }],
      context: { eventName: event.eventName },
    })
    expect(published.status, JSON.stringify(published.body)).toBe(201)
    expect(published.body).toMatchObject({ created: 0, skipped: { actor: 1 } })
  })

  test('TC-SPM93-AC06 one notification is created per recipient per occurrence of a trigger', async () => {
    const eventId = `AUTO-SPM93-repeat-${Date.now()}`
    const occurrence = {
      trigger: 'booking.assigned',
      occurrenceId: `${eventId}:booking.assigned:1`,
      eventId,
      recipients: [
        { userId: 'u2', role: 'coordinator' },
        { userId: 'u2', role: 'coordinator' },
        { userId: 'u6', role: 'coordinator' },
      ],
      context: { eventName: 'AUTO SPM-93 repeat' },
    }
    const first = await publish(occurrence)
    expect(first.status, JSON.stringify(first.body)).toBe(201)
    expect(first.body).toMatchObject({ created: 2, skipped: { duplicate: 1 } })
    // The same occurrence again (a retry) notifies nobody twice.
    const again = await publish(occurrence)
    // Skipped: u2 listed twice, plus u2 and u6 already notified for this occurrence.
    expect(again.body).toMatchObject({ created: 0, skipped: { duplicate: 3 } })
    expect(await inbox('EC-01', eventId)).toHaveLength(1)
    expect(await inbox('EC-02', eventId)).toHaveLength(1)
  })

  test('TC-SPM93-AC07 an attendee receives only a notification whose trigger is attendee-visible', async () => {
    const eventId = `AUTO-SPM93-attendee-${Date.now()}`
    const internal = await publish({
      trigger: 'booking.assigned',
      occurrenceId: `${eventId}:internal`,
      eventId,
      recipients: [{ userId: 'u5', role: 'attendee' }],
      context: { eventName: 'AUTO SPM-93 attendee' },
    })
    expect(internal.body).toMatchObject({ created: 0, skipped: { attendeeHidden: 1 } })
    expect(await inbox('ATT-01', eventId)).toEqual([])

    const visible = await publish({
      trigger: 'event.cancelled',
      occurrenceId: `${eventId}:visible`,
      eventId,
      recipients: [{ userId: 'u5', role: 'attendee' }],
      context: { eventName: 'AUTO SPM-93 attendee', reason: 'AUTO' },
    })
    expect(visible.body).toMatchObject({ created: 1 })
    expect(types(await inbox('ATT-01', eventId))).toEqual(['event.cancelled'])
  })

  test('TC-SPM93-AC08 every message names the event and states what happened in plain language', async () => {
    const event = await assignedEvent('wording')
    const rows = [...(await inbox('EC-01', event.eventId)), ...(await inbox('EO-01', event.eventId))]
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      const text = `${row.title} ${row.body}`
      expect(text).toContain(event.eventName)
      // Plain language: no trigger keys or raw status codes (contact emails aside).
      expect(text.replace(/\S+@\S+/g, '')).not.toMatch(/\b[a-z_]+\.[a-z_]+\b|under_review|\bsubmitted\b/)
    }
  })

  // Making delivery fail needs the notification service to refuse or be down while the action
  // runs, which an end-to-end run cannot arrange. Covered by unit tests instead:
  // event-service test_event_assignment (send failure), test_event_reminders (refused publish),
  // registration-service test_registration_withdrawal, venue-service test_venue_replacement_routes.
  test.skip('TC-SPM93-AC09 if delivery fails, the action still succeeds and the failure is logged', async () => {})

  test('TC-SPM93-AC10 notifications remain after the event is completed', async () => {
    test.setTimeout(120_000)
    const event = await readyToConfirm('SPM93-completed')
    const confirmed = await confirm(event)
    expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)
    const before = (await inbox('EC-01', event.eventId)).map((row) => row.notificationId)
    expect(before.length).toBeGreaterThan(0)

    endInThePast(event.eventId)
    const completed = await events('POST', `/${event.eventId}/complete`, 'EC-01')
    expect(completed.status, JSON.stringify(completed.body)).toBe(200)
    expect(completed.body.status).toBe('completed')

    const after = (await inbox('EC-01', event.eventId)).map((row) => row.notificationId)
    expect(after).toEqual(expect.arrayContaining(before))
  })

  test('TC-SPM93-AC10 notifications remain after the event is cancelled', async () => {
    const event = await assignedEvent('persist')
    const cancelled = await cancel(event, 'EO-01')
    expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200)
    expect(cancelled.body.status).toMatch(/cancelled/i)
    await eventuallyContains('EC-01', event.eventId, 'event.cancelled')
    expect(types(await inbox('EC-01', event.eventId))).toContain('booking.assigned')
    expect(types(await inbox('EO-01', event.eventId))).toContain('event.coordinator')
  })
})
