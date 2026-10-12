import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { events } from './support/confirmation.js'
import { assignCoordinator, createSubmittedEvent } from './support/event.js'
import { notificationApi } from './support/registration.js'

// SPM-118: the Event Coordinator Lead (ECL-01, u14) moves an event from its
// current Event Coordinator (EC-01, u2) to a different one (EC-02, u6).

async function assignedToBen(label) {
  const event = await createSubmittedEvent('EO-01', `AUTO-SPM118-${label}-${Date.now()}`)
  await assignCoordinator(event.eventId, 'u2')
  return event
}

async function coordinatorOf(event) {
  return (await events('GET', `/${event.eventId}`, 'ECL-01')).body.coordinatorId
}

// A quiet edit the assigned coordinator may make (SPM-71).
function edit(event, accountId) {
  return events('PATCH', `/${event.eventId}`, accountId, { description: `Edited by ${accountId}` })
}

async function inbox(accountId) {
  return JSON.stringify((await notificationApi('GET', '/notifications', accountId)).body)
}

test.describe('SPM-118 Reassign an event to another Event Coordinator', () => {
  test('TC-SPM118-AC01 the Lead reassigns an event from its current coordinator to a different one', async ({ page }) => {
    const event = await assignedToBen('ac01')
    await login(page, account('ECL-01'))
    await page.goto(`/app/events/${event.eventId}`)
    await page.getByTestId('assign-coordinator').click()
    // The current coordinator cannot be chosen; a reassignment needs someone else.
    await expect(page.getByTestId('assign-candidate-u2')).toBeDisabled()
    await expect(page.getByTestId('assign-confirm')).toBeDisabled()
    await page.getByTestId('assign-candidate-u6').click()
    const reassigned = page.waitForResponse(
      (response) => /\/assign-coordinator$/.test(response.url()) && response.request().method() === 'POST',
    )
    await page.getByTestId('assign-confirm').click()
    expect((await reassigned).status()).toBe(201)
    await expect(page.getByTestId('assign-dialog')).toHaveCount(0)
    expect(await coordinatorOf(event)).toBe('u6')

    const same = await events('POST', `/${event.eventId}/assign-coordinator`, 'ECL-01', { coordinatorId: 'u6' })
    expect(same.status).toBe(409)
    expect(same.body.detail).toContain('already the coordinator')
  })

  test('TC-SPM118-AC02 an Event Coordinator who tries to reassign an event gets 403', async () => {
    const event = await assignedToBen('ac02')
    // Neither the current coordinator handing it on, nor another taking it.
    for (const [accountId, coordinatorId] of [
      ['EC-01', 'u6'],
      ['EC-02', 'u6'],
    ]) {
      const denied = await events('POST', `/${event.eventId}/assign-coordinator`, accountId, { coordinatorId })
      expect(denied.status, accountId).toBe(403)
    }
    expect(await coordinatorOf(event)).toBe('u2')
  })

  test('TC-SPM118-AC03 reassignment immediately removes edit permission from the previous coordinator and grants it to the new one', async () => {
    const event = await assignedToBen('ac03')
    expect((await edit(event, 'EC-01')).status).toBe(200)
    expect((await edit(event, 'EC-02')).status).toBe(403)

    await assignCoordinator(event.eventId, 'u6')

    // Same sessions, no sign-in again: the very next requests see the change.
    expect((await edit(event, 'EC-01')).status).toBe(403)
    expect((await edit(event, 'EC-02')).status).toBe(200)
  })

  test('TC-SPM118-AC04 the activity log records who reassigned it, who was assigned, and when', async () => {
    const event = await assignedToBen('ac04')
    await assignCoordinator(event.eventId, 'u6')

    const log = await events('GET', `/${event.eventId}/activity-log`, 'ECL-01')
    const reassignment = log.body.filter((entry) => entry.kind === 'assignment').at(-1)
    expect(reassignment).toMatchObject({ changedBy: 'u14', oldValue: 'u2', newValue: 'u6' })
    expect(reassignment.createdAt).toBeTruthy()
  })

  test('TC-SPM118-AC05 the new coordinator, the previous coordinator, and the Event Organiser are notified', async () => {
    const event = await assignedToBen('ac05')
    await assignCoordinator(event.eventId, 'u6')

    expect(await inbox('EC-02')).toContain(`${event.eventName} has been assigned to you`)
    expect(await inbox('EC-01')).toContain(`${event.eventName} has been reassigned`)
    expect(await inbox('EO-01')).toContain(`Cara Ng is now your coordinator for ${event.eventName}`)
  })
})
