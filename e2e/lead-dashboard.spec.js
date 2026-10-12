import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { events } from './support/confirmation.js'
import { assignCoordinator, createSubmittedEvent } from './support/event.js'

// Prototype: the Event Coordinator Lead's dashboard (no story yet). It reads only
// the Lead's queue (SPM-117) and assignments (SPM-119), so it checks against those.

test.describe('Lead dashboard prototype', () => {
  test('the Lead sees live counts, the longest-waiting unassigned requests, and each coordinator workload', async ({
    page,
  }, testInfo) => {
    const caras = await createSubmittedEvent('EO-01', `AUTO-LEADDASH-${Date.now()}`)
    await assignCoordinator(caras.eventId, 'u6')
    const queue = (await events('GET', '/queue', 'ECL-01')).body
    const unassigned = queue.filter((event) => !event.coordinatorId)
    const groups = (await events('GET', '/assignments', 'ECL-01')).body
    const activeOf = (userId) => groups.find((group) => group.userId === userId).events.length

    await login(page, account('ECL-01'))
    const dashboard = page.getByTestId('lead-dashboard')
    await expect(dashboard).toBeVisible()
    await expect(page.getByTestId('lead-count-unassigned')).toContainText(String(unassigned.length))
    await expect(page.getByTestId('lead-count-active')).toContainText(
      String(groups.reduce((sum, group) => sum + group.events.length, 0)),
    )
    if (unassigned.length) {
      // Longest-waiting first, as the queue orders them.
      await expect(page.getByTestId(`lead-waiting-${unassigned[0].eventId}`)).toBeVisible()
      // Assign opens the coordinator dialog; cancelled here so seeded requests stay unassigned.
      await page.getByTestId(`lead-assign-${unassigned[0].eventId}`).click()
      await expect(page.getByTestId('assign-dialog')).toBeVisible()
      await page.getByTestId('assign-dialog').getByRole('button', { name: 'Cancel' }).click()
    }
    for (const userId of ['u2', 'u6']) {
      await expect(page.getByTestId(`lead-workload-${userId}`).getByTestId('lead-workload-count')).toHaveText(
        String(activeOf(userId)),
      )
    }
    await page.screenshot({ path: testInfo.outputPath('lead-dashboard.png') })
    // The main area scrolls on its own, so the workload needs its own picture.
    await page.getByTestId('lead-workload-u2').scrollIntoViewIfNeeded()
    await page.screenshot({ path: testInfo.outputPath('lead-dashboard-workload.png') })

    await page.getByTestId('lead-workload-u6').click()
    await expect(page.getByTestId('coordinator-assignments')).toBeVisible()
    await expect(page.getByTestId(`assignments-event-${caras.eventId}`)).toBeVisible()
  })

  test('an Event Coordinator does not get the Lead dashboard', async ({ page }) => {
    await login(page, account('EC-01'))
    await expect(page.locator('.nav-item').getByText('Review Queue', { exact: true })).toBeVisible()
    await expect(page.getByTestId('lead-dashboard')).toHaveCount(0)
  })
})
