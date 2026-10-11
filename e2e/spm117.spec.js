import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { events } from './support/confirmation.js'
import { assignCoordinator, createSubmittedEvent } from './support/event.js'
import { notificationApi } from './support/registration.js'

// SPM-117: an Event Coordinator Lead (ECL-01, u14) assigns each new request to
// an Event Coordinator. Reassignment is SPM-118; the all-assignments view is SPM-119.

async function newRequest(label) {
  return createSubmittedEvent('EO-01', `AUTO-SPM117-${label}-${Date.now()}`)
}

async function inbox(accountId) {
  return JSON.stringify((await notificationApi('GET', '/notifications', accountId)).body)
}

test.describe('SPM-117 Assign an unassigned request to an Event Coordinator', () => {
  test('TC-SPM117-AC01 an Event Coordinator Lead can sign in with a pre-created account', async ({ page }) => {
    await login(page, account('ECL-01'))
    await expect(page.locator('.role-label')).toContainText('Rachel Goh (Event Coordinator Lead)')
  })

  test('TC-SPM117-AC02 a newly submitted request stays unassigned until the Lead assigns it', async () => {
    const event = await newRequest('ac02')
    expect(event.coordinatorId).toBeFalsy()
    const stored = await events('GET', `/${event.eventId}`, 'ECL-01')
    expect(stored.body).toMatchObject({ status: 'submitted', coordinatorId: null })

    await assignCoordinator(event.eventId, 'u2')
    expect((await events('GET', `/${event.eventId}`, 'ECL-01')).body.coordinatorId).toBe('u2')
  })

  test('TC-SPM117-AC03 the Lead sees unassigned requests in the review queue with name, organisation, date and time, attendance, and submission time', async ({
    page,
  }) => {
    const event = await newRequest('ac03')
    await login(page, account('ECL-01'))
    await page.locator('.nav-item').getByText('Review Queue', { exact: true }).click()
    await page.getByTestId('queue-filter-unassigned').click()
    const row = page.getByTestId(`review-queue-${event.eventId}`)
    await expect(row).toHaveAttribute('data-assigned', 'false')
    await expect(row).toContainText(event.eventName)
    await expect(row).toContainText('Apex Partners')
    await expect(row.getByTestId('queue-datetime')).not.toBeEmpty()
    await expect(row.getByTestId('queue-attendance')).toContainText(`${event.expectedAttendance} attendees`)
    await expect(row.getByTestId('queue-submitted-at')).toContainText('Submitted')
  })

  test('TC-SPM117-AC04 the Lead can assign one of those requests to an Event Coordinator', async ({ page }) => {
    const event = await newRequest('ac04')
    await login(page, account('ECL-01'))
    await page.locator('.nav-item').getByText('Review Queue', { exact: true }).click()
    await page.getByTestId(`review-queue-${event.eventId}`).click()
    await page.getByTestId('queue-assign-coordinator').click()
    await page.getByTestId('assign-candidate-u2').click()
    const assigned = page.waitForResponse(
      (response) => /\/assign-coordinator$/.test(response.url()) && response.request().method() === 'POST',
    )
    await page.getByTestId('assign-confirm').click()
    expect((await assigned).status()).toBe(201)
    await expect(page.getByTestId('assign-dialog')).toHaveCount(0)

    const stored = await events('GET', `/${event.eventId}`, 'ECL-01')
    expect(stored.body).toMatchObject({ coordinatorId: 'u2', status: 'under review' })
  })

  test('TC-SPM117-AC05 an Event Coordinator who tries to assign a request gets 403', async () => {
    const event = await newRequest('ac05')
    for (const accountId of ['EC-01', 'EC-02']) {
      const denied = await events('POST', `/${event.eventId}/assign-coordinator`, accountId, { coordinatorId: 'u2' })
      expect(denied.status, accountId).toBe(403)
    }
    expect((await events('GET', `/${event.eventId}`, 'ECL-01')).body.coordinatorId).toBeNull()
  })

  test('TC-SPM117-AC06 the activity log records who assigned it, who was assigned, and when', async () => {
    const event = await newRequest('ac06')
    await assignCoordinator(event.eventId, 'u2')

    const log = await events('GET', `/${event.eventId}/activity-log`, 'ECL-01')
    expect(log.status).toBe(200)
    const [assignment] = log.body.filter((entry) => entry.kind === 'assignment')
    expect(assignment).toMatchObject({ changedBy: 'u14', newValue: 'u2' })
    expect(assignment.createdAt).toBeTruthy()
  })

  test('TC-SPM117-AC07 the newly assigned coordinator and the Event Organiser are notified', async () => {
    const event = await newRequest('ac07')
    await assignCoordinator(event.eventId, 'u2')
    expect(await inbox('EC-01')).toContain(`You are now the coordinator for ${event.eventName}`)
    expect(await inbox('EO-01')).toContain(`Ben Lee is now your coordinator for ${event.eventName}`)
  })
})
