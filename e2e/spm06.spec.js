import { test, expect } from '@playwright/test'
import { assignCoordinator, createSubmittedEvent, eventApi } from './support/event.js'
import { notificationApi } from './support/registration.js'

// Each test looks only at clarification.replied notices on its own event, and tells a new
// one from an older one by its id, so earlier replies in the same run cannot satisfy it.

async function replyNotices(eventId) {
  const inbox = await notificationApi('GET', '/notifications?pageSize=100', 'EC-01')
  expect(inbox.status, JSON.stringify(inbox.body)).toBe(200)
  return inbox.body.filter((row) => row.eventId === eventId && row.type === 'clarification.replied')
}

// Replies as the organiser and returns the one notice that reply created.
async function replyAndGetNotice(eventId, clarificationId, message) {
  const before = (await replyNotices(eventId)).map((row) => row.notificationId)
  const reply = await eventApi('POST', `/${eventId}/clarifications/${clarificationId}/reply`, 'EO-01', { message })
  expect(reply.status, JSON.stringify(reply.body)).toBe(201)
  const added = (await replyNotices(eventId)).filter((row) => !before.includes(row.notificationId))
  expect(added).toHaveLength(1)
  return added[0]
}

test.describe('SPM-06 Clarification on assigned request', () => {
  test('TC-SPM06-AC01 when the organiser responds to a clarification, the assigned coordinator is notified', async () => {
    const notice = await replyAndGetNotice('e3', 'rv-clarify-e3', `Attendance stays at 80. ${Date.now()}`)
    expect(notice.userId).toBe('u2')
    expect(notice.isRead).toBe(false)
  })

  test('TC-SPM06-AC02 the notification names the event and includes the response or a link to it', async () => {
    const message = `HDMI is required at the lectern. ${Date.now()}`
    const notice = await replyAndGetNotice('e3', 'rv-clarify-e3', message)
    expect(notice.title).toContain('Partner Networking Night')
    expect(notice.body).toContain('Partner Networking Night')
    expect(notice.body).toContain(message)
    expect(notice.link).toBe('/app/events/e3')
  })

  test('TC-SPM06-AC03 no notification is generated before the organiser responds; the clarification stays outstanding', async () => {
    const event = await createSubmittedEvent('EO-01', `AUTO-SPM06-waiting-${Date.now()}`)
    await assignCoordinator(event.eventId, 'u2')
    const raised = await eventApi('POST', `/${event.eventId}/clarifications`, 'EC-01', {
      message: 'Please confirm the expected attendance.',
      field: 'expectedAttendance',
    })
    expect(raised.status, JSON.stringify(raised.body)).toBe(201)
    const clarificationId = raised.body.clarificationId

    const threads = await eventApi('GET', `/${event.eventId}/clarifications`, 'EC-01')
    expect(threads.status, JSON.stringify(threads.body)).toBe(200)
    expect(threads.body.find((row) => row.clarificationId === clarificationId).status).toBe('open')
    expect(await replyNotices(event.eventId)).toEqual([])

    // The check above would pass on a broken trigger too, so prove the reply does notify.
    await replyAndGetNotice(event.eventId, clarificationId, `Attendance is 50. ${Date.now()}`)
  })

  test('TC-SPM06-AC04 a late response still notifies, and flags that the request is no longer awaiting review', async () => {
    const message = `Late answer after planning moved on. ${Date.now()}`
    const notice = await replyAndGetNotice('e1', 'late-reply', message)
    expect(notice.title).toContain('AI in Events Summit')
    expect(notice.body).toContain(message)
    expect(notice.body).toMatch(/no longer awaiting review/i)
  })
})
