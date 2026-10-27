import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'

// SPM-47 in the browser. Seeded events are read, never changed (see spm47-api.spec.js).

test.describe('SPM-47 Multi-Tenant Event Access Restriction (UI)', () => {
  test('TC-SPM47-AC01 My Events lists the organisation\'s events and none of another organisation\'s', async ({ page }) => {
    // The whole organisation's list loads at once; a database that earlier runs filled
    // with test events makes it slow, so wait for the list rather than a fixed time.
    test.slow()
    await login(page, account('EO-03'))

    await page.getByRole('navigation').getByText('My Events', { exact: true }).click()
    await expect(page.getByText('Loading your events…')).toHaveCount(0, { timeout: 90_000 })

    // e1 was filed by EO-01, EO-03's colleague (AC2).
    await expect(page.getByText('AI in Events Summit').first()).toBeVisible()
    await expect(page.getByText('Colleague Town Hall').first()).toBeVisible()
    await expect(page.getByText('Beacon Q4 Showcase')).toHaveCount(0)
  })

  test('TC-SPM47-AC03 another organisation\'s event URL shows nothing of it', async ({ page }) => {
    await login(page, account('EO-01'))

    await page.goto('/app/events/e5')

    await expect(page.getByText('This event is no longer available to you.')).toBeVisible()
    await expect(page.getByText('Beacon Q4 Showcase')).toHaveCount(0)
  })

  test('TC-SPM47-AC04 a colleague\'s event opens', async ({ page }) => {
    await login(page, account('EO-03'))

    await page.goto('/app/events/e1')

    await expect(page.getByRole('heading', { name: 'AI in Events Summit' })).toBeVisible()
  })
})
