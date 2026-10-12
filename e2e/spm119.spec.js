import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { events } from './support/confirmation.js'
import { assignCoordinator, createSubmittedEvent } from './support/event.js'

// SPM-119: the Event Coordinator Lead (ECL-01) sees every Event Coordinator and
// the active events assigned to them; Event Coordinators do not.

async function assignedTo(coordinatorId, label) {
  const event = await createSubmittedEvent('EO-01', `AUTO-SPM119-${label}-${Date.now()}`)
  await assignCoordinator(event.eventId, coordinatorId)
  return event
}

async function assignments(accountId) {
  return events('GET', '/assignments', accountId)
}

function eventsOf(groups, coordinatorId) {
  return (groups.find((group) => group.userId === coordinatorId)?.events || []).map((event) => event.eventId)
}

test.describe("SPM-119 View every coordinator's assignments and active events", () => {
  test('TC-SPM119-AC01 the Lead sees each Event Coordinator and the active events assigned to them', async ({ page }) => {
    const bens = await assignedTo('u2', 'ben')
    const caras = await assignedTo('u6', 'cara')
    const finished = await assignedTo('u2', 'rejected')
    const rejected = await events('POST', `/${finished.eventId}/reject`, 'EC-01', { reason: 'AUTO-SPM119' })
    expect(rejected.status).toBe(200)

    const view = await assignments('ECL-01')
    expect(view.status).toBe(200)
    expect(eventsOf(view.body, 'u2')).toContain(bens.eventId)
    expect(eventsOf(view.body, 'u2')).not.toContain(caras.eventId)
    expect(eventsOf(view.body, 'u6')).toContain(caras.eventId)
    // A rejected event is no longer active.
    expect(eventsOf(view.body, 'u2')).not.toContain(finished.eventId)

    await login(page, account('ECL-01'))
    await page.locator('.nav-item').getByText('Assignments', { exact: true }).click()
    const ben = page.getByTestId('assignments-coordinator-u2')
    await expect(ben).toContainText('Ben Lee')
    await expect(ben.getByTestId(`assignments-event-${bens.eventId}`)).toContainText(bens.eventName)
    await expect(ben.getByTestId(`assignments-event-${caras.eventId}`)).toHaveCount(0)
    await expect(
      page.getByTestId('assignments-coordinator-u6').getByTestId(`assignments-event-${caras.eventId}`),
    ).toBeVisible()
  })

  test('TC-SPM119-AC02 the Lead can open any of those events', async ({ page }) => {
    const caras = await assignedTo('u6', 'open')
    await login(page, account('ECL-01'))
    await page.locator('.nav-item').getByText('Assignments', { exact: true }).click()
    await page.getByTestId(`assignments-event-${caras.eventId}`).click()
    await expect(page).toHaveURL(new RegExp(`/app/events/${caras.eventId}$`))
    await expect(page.getByRole('heading', { name: caras.eventName })).toBeVisible()
  })

  test('TC-SPM119-AC03 an Event Coordinator does not get the all-assignments view and manages only their own events', async ({
    page,
  }) => {
    for (const accountId of ['EC-01', 'EC-02']) {
      expect((await assignments(accountId)).status, accountId).toBe(403)
    }
    await login(page, account('EC-01'))
    await expect(page.locator('.nav-item').getByText('Review Queue', { exact: true })).toBeVisible()
    await expect(page.locator('.nav-item').getByText('Assignments', { exact: true })).toHaveCount(0)

    const bens = await assignedTo('u2', 'own')
    const edited = await events('PATCH', `/${bens.eventId}`, 'EC-02', { description: 'Not theirs' })
    expect(edited.status).toBe(403)
    const approved = await events('POST', `/${bens.eventId}/approve`, 'EC-02', {})
    expect(approved.status).toBe(403)
    expect((await events('PATCH', `/${bens.eventId}`, 'EC-01', { description: 'Theirs' })).status).toBe(200)
  })
})
