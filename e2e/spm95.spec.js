import { test, expect } from '@playwright/test'
import { EVENT_REMINDER_LEAD_DAYS, newEventPayload, venuePeriod } from './support/api-data.js'
import { events } from './support/confirmation.js'
import { assignCoordinator } from './support/event.js'
import { notificationApi } from './support/registration.js'

// The check runs through event-service's POST /events/reminders/run, which the
// daily job calls with the service key and a coordinator or the Lead can call on
// demand. No seeded event starts inside the lead time, so each test makes its own.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// The event date as reminders write it: "%d %b %Y" in Singapore time.
function sgtDate(iso) {
  const sgt = new Date(new Date(iso).getTime() + 8 * 60 * 60 * 1000)
  return `${String(sgt.getUTCDate()).padStart(2, '0')} ${MONTHS[sgt.getUTCMonth()]} ${sgt.getUTCFullYear()}`
}

// An event starting `days` from now. By default it is assigned to EC-01 (u2) and
// approved, so it is in planning with no venue booked; `equipment` adds one line.
async function approachingEvent(label, { days = 3, equipment = false, assign = true, approve = true } = {}) {
  const period = venuePeriod(days)
  const { registrationEnabled, capacity, ...fields } = newEventPayload(`AUTO-SPM95-${label}-${Date.now()}`)
  const draft = await events('POST', '/drafts', 'EO-01', {
    ...fields,
    proposedStartAt: period.startsAt,
    proposedEndAt: period.endsAt,
    ...(equipment ? { equipmentLines: [{ equipmentId: 'eq1', quantity: 1 }] } : {}),
  })
  expect(draft.status, JSON.stringify(draft.body)).toBe(201)
  const submitted = await events('POST', `/${draft.body.eventId}/submit`, 'EO-01')
  expect(submitted.status, JSON.stringify(submitted.body)).toBe(200)
  if (assign) await assignCoordinator(draft.body.eventId, 'u2')
  if (assign && approve) {
    const approved = await events('POST', `/${draft.body.eventId}/approve`, 'EC-01', {})
    expect(approved.status, JSON.stringify(approved.body)).toBe(200)
  }
  return { eventId: draft.body.eventId, eventName: fields.eventName, startsAt: period.startsAt }
}

async function run(accountId = 'EC-01') {
  const result = await events('POST', '/reminders/run', accountId)
  expect(result.status, JSON.stringify(result.body)).toBe(200)
  return result.body
}

function reminded(result, event) {
  return result.reminded.find((row) => row.eventId === event.eventId)
}

function looked(result, event) {
  return [...result.reminded, ...result.skipped].some((row) => row.eventId === event.eventId)
}

async function inbox(accountId, event, type) {
  const listed = await notificationApi('GET', '/notifications?pageSize=100', accountId)
  expect(listed.status, JSON.stringify(listed.body)).toBe(200)
  return listed.body.filter((row) => row.eventId === event.eventId && row.type === type)
}

test.describe('SPM-95 Remind staff of approaching events with outstanding arrangements', () => {
  // Each run checks every approaching event in the database, and some tests run it more than once.
  test.describe.configure({ timeout: 180_000 })

  test('TC-SPM95-AC01 the check selects events within the lead time whose readiness still shows an outstanding arrangement', async () => {
    const near = await approachingEvent('near')
    const far = await approachingEvent('far', { days: EVENT_REMINDER_LEAD_DAYS + 2 })
    const result = await run()
    expect(reminded(result, near), 'approaching event is reminded').toBeTruthy()
    expect(looked(result, far), 'event beyond the lead time is not looked at').toBe(false)
    const ranAt = Date.parse(`${result.ranAt}Z`.replace(/ZZ$/, 'Z'))
    for (const row of result.reminded) {
      const days = (Date.parse(`${row.proposedStartAt}Z`.replace(/ZZ$/, 'Z')) - ranAt) / 86400000
      expect(days).toBeLessThanOrEqual(result.leadDays)
      expect(row.outstanding.length, `${row.eventId} has something outstanding`).toBeGreaterThan(0)
    }
  })

  test('TC-SPM95-AC02 each selected event notifies its assigned coordinator, naming the event, its date, and what is outstanding', async () => {
    const event = await approachingEvent('coordinator')
    const row = reminded(await run(), event)
    expect(row).toMatchObject({ coordinatorId: 'u2' })
    expect(row.sent).toContain('readiness.reminder')
    const notes = await inbox('EC-01', event, 'readiness.reminder')
    expect(notes).toHaveLength(1)
    expect(notes[0].body).toContain(event.eventName)
    expect(notes[0].body).toContain(sgtDate(event.startsAt))
    expect(notes[0].body).toMatch(/Venue/)
  })

  test('TC-SPM95-AC03 an outstanding venue also notifies Venue Staff, and outstanding equipment Technical Support Staff', async () => {
    const event = await approachingEvent('staff', { equipment: true })
    const row = reminded(await run(), event)
    expect(row.sent).toEqual(expect.arrayContaining(['readiness.reminder.venue', 'readiness.reminder.equipment']))
    const venue = await inbox('VS-01', event, 'readiness.reminder.venue')
    const equipment = await inbox('TS-01', event, 'readiness.reminder.equipment')
    expect(venue).toHaveLength(1)
    expect(equipment).toHaveLength(1)
    expect(venue[0].body).toContain(event.eventName)
    expect(equipment[0].body).toContain(event.eventName)
  })

  test('TC-SPM95-AC04 the lead time is configuration read from one place', async () => {
    const inside = await approachingEvent('inside', { days: EVENT_REMINDER_LEAD_DAYS - 1 })
    const outside = await approachingEvent('outside', { days: EVENT_REMINDER_LEAD_DAYS + 1 })
    const result = await run()
    // The check reports the configured value (EVENT_REMINDER_LEAD_DAYS) and selects by it.
    expect(result.leadDays).toBe(EVENT_REMINDER_LEAD_DAYS)
    expect(reminded(result, inside)).toBeTruthy()
    expect(looked(result, outside)).toBe(false)
  })

  test('TC-SPM95-AC05 a reminder is raised once per event per occasion, so a repeat check does not notify again', async () => {
    const event = await approachingEvent('once')
    await run()
    await run()
    expect(await inbox('EC-01', event, 'readiness.reminder')).toHaveLength(1)
    expect(await inbox('VS-01', event, 'readiness.reminder.venue')).toHaveLength(1)
  })

  test('TC-SPM95-AC06 a fully ready, completed, cancelled, or rejected event produces no reminder', async () => {
    const cancelled = await approachingEvent('cancelled')
    const cancel = await events('POST', `/${cancelled.eventId}/cancel`, 'EC-01', { reason: 'AUTO-SPM95' })
    expect(cancel.status, JSON.stringify(cancel.body)).toBe(200)

    const rejected = await approachingEvent('rejected', { approve: false })
    const reject = await events('POST', `/${rejected.eventId}/reject`, 'EC-01', {
      reason: 'insufficient notice',
      explanation: 'AUTO-SPM95',
    })
    expect(reject.status, JSON.stringify(reject.body)).toBe(200)

    const result = await run()
    expect(looked(result, cancelled)).toBe(false)
    expect(looked(result, rejected)).toBe(false)
    // An event with nothing outstanding is never reminded.
    for (const row of result.reminded) expect(row.outstanding.length).toBeGreaterThan(0)
    expect(await inbox('EC-01', cancelled, 'readiness.reminder')).toEqual([])
    expect(await inbox('EC-01', rejected, 'readiness.reminder')).toEqual([])
  })

  test('TC-SPM95-AC07 an approaching event with no coordinator assigned notifies the Event Coordinator Lead', async () => {
    const event = await approachingEvent('unassigned', { assign: false })
    const row = reminded(await run(), event)
    expect(row).toMatchObject({ coordinatorId: null })
    expect(row.sent).toContain('readiness.reminder.unassigned')
    const notes = await inbox('ECL-01', event, 'readiness.reminder.unassigned')
    expect(notes).toHaveLength(1)
    expect(notes[0].body).toContain(event.eventName)
    expect(notes[0].body).toContain(sgtDate(event.startsAt))
  })

  test('TC-SPM95-AC08 the check can be run on demand in the demo environment', async () => {
    const before = Date.now()
    const byCoordinator = await run('EC-01')
    expect(Date.parse(`${byCoordinator.ranAt}Z`.replace(/ZZ$/, 'Z'))).toBeGreaterThanOrEqual(before - 60_000)
    await run('ECL-01')
    const byOrganiser = await events('POST', '/reminders/run', 'EO-01')
    expect(byOrganiser.status).toBe(403)
  })
})
