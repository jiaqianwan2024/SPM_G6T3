import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { THEATRE_EVENT, approvedEvent } from './support/venue-request.js'
import { assignCoordinator } from './support/event.js'

// Each test makes its own event, approved for planning and assigned to EC-01 (u2).

async function openEvent(page, id, event) {
  await login(page, account(id))
  await page.goto(`/app/events/${event.eventId}`)
  await expect(page.getByRole('heading', { name: event.eventName })).toBeVisible()
}

function planningControls(page) {
  return {
    edit: page.getByTestId('event-edit'),
    chooseVenue: page.getByTestId('event-choose-venue'),
    requestEquipment: page.getByRole('button', { name: 'Add to request' }),
  }
}

test.describe('SPM-46 Assigned Coordinator Event Permissions (UI)', () => {
  test('TC-SPM46-AC01 assigned coordinator has the planning controls on event details', async ({ page }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    await openEvent(page, 'EC-01', event)

    const controls = planningControls(page)
    await expect(controls.edit).toBeVisible()
    await expect(controls.chooseVenue).toBeVisible()
    await expect(controls.requestEquipment).toBeVisible()

    await controls.chooseVenue.click()
    await page.getByTestId('venue-select-v1').click()
    await expect(page.getByTestId('suitability-verdict')).toBeVisible()
    await expect(page.getByTestId('venue-request-submit')).toBeVisible()
    await expect(page.getByTestId('venue-request-read-only')).toHaveCount(0)
  })

  test('TC-SPM46-AC01 only the assigned coordinator is offered the confirmation panel', async ({ page, browser }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    await openEvent(page, 'EC-01', event)
    await expect(page.getByTestId('event-confirmation')).toBeVisible()

    const other = await browser.newPage()
    await openEvent(other, 'EC-02', event)
    await expect(other.getByTestId('event-confirmation')).toHaveCount(0)
    await other.close()
  })

  for (const id of ['EC-02', 'VS-01', 'TS-01']) {
    test(`TC-SPM46-AC02 ${id} sees another coordinator's event read-only`, async ({ page }) => {
      const event = await approvedEvent(THEATRE_EVENT)
      await openEvent(page, id, event)

      const controls = planningControls(page)
      await expect(controls.edit).toHaveCount(0)
      await expect(controls.chooseVenue).toHaveCount(0)
      await expect(controls.requestEquipment).toHaveCount(0)
      await expect(page.getByTestId('event-approve')).toHaveCount(0)
      await expect(page.getByTestId('event-registration-settings-link')).toHaveCount(0)
      await expect(page.getByTestId('event-discard')).toHaveCount(0)
    })
  }

  test('TC-SPM46-AC02 an unassigned coordinator can check venues but not request one', async ({ page }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    await login(page, account('EC-02'))
    await page.goto(`/app/events/${event.eventId}/venues`)

    await expect(page.getByTestId('venue-request-read-only')).toHaveText(
      'Only the coordinator assigned to this event can request, withdraw, or cancel a venue for it. You can still check how each venue suits the event.',
    )
    await page.getByTestId('venue-select-v1').click()
    await expect(page.getByTestId('suitability-verdict')).toBeVisible()
    await expect(page.getByTestId('venue-request-submit')).toHaveCount(0)
    await expect(page.getByTestId('venue-request-notes')).toHaveCount(0)
  })

  test('TC-SPM46-AC03 reassignment swaps the planning controls without signing out', async ({ page }) => {
    const event = await approvedEvent(THEATRE_EVENT)
    await openEvent(page, 'EC-01', event)
    const controls = planningControls(page)
    await expect(controls.edit).toBeVisible()

    // Only the Event Coordinator Lead reassigns; EC-01 has no Assign button.
    await expect(page.getByTestId('assign-coordinator')).toHaveCount(0)
    await assignCoordinator(event.eventId, 'u6')
    await page.reload()

    await expect(controls.edit).toHaveCount(0)
    await expect(controls.chooseVenue).toHaveCount(0)
    await expect(controls.requestEquipment).toHaveCount(0)

    await page.goto('/app')
    await page.getByRole('button', { name: 'Log out' }).click()
    await openEvent(page, 'EC-02', event)
    await expect(controls.edit).toBeVisible()
    await expect(controls.chooseVenue).toBeVisible()
    await expect(controls.requestEquipment).toBeVisible()
  })
})
