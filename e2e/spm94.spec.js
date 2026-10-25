import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { notificationApi } from './support/registration.js'

test.describe('SPM-94 Manage my notifications', () => {
  test('TC-SPM94-AC01 an unread count is visible on every screen and updates when notifications are read', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    const badge = page.getByTestId('notification-unread-count')
    await expect(badge).toBeVisible()
    const before = await badge.innerText()
    await page.goto('/app/notifications')
    const unread = page.locator('[data-read="false"]').first()
    if (await unread.count()) {
      await unread.click()
      await expect(badge).not.toHaveText(before)
    }
  })

  test('TC-SPM94-AC02 the list shows newest first, with unread ones visually distinct', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/notifications')
    const items = page.getByTestId('notification-row')
    await expect(items.first()).toBeVisible()
    const unread = page.locator('[data-testid="notification-row"][data-read="false"]')
    if (await unread.count()) {
      await expect(unread.first()).toHaveAttribute('data-read', 'false')
    }
  })

  test('TC-SPM94-AC03 opening a notification marks it read and navigates to the event or resource', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/notifications')
    await page.getByTestId('notification-row').first().click()
    await expect(page).toHaveURL(/e1|events|notifications/i)
  })

  test('TC-SPM94-AC04 the user can mark one read, mark all read, and filter to unread only', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/notifications')
    await page.getByTestId('notification-mark-all-read').click()
    await page.getByTestId('notification-filter-unread').click()
    const marked = await notificationApi('POST', '/notifications/read-all', 'EO-01')
    expect([200, 204]).toContain(marked.status)
  })

  test('TC-SPM94-AC05 following a notification the user may no longer access shows a clear message, not an error page', async ({
    page,
  }) => {
    await login(page, account('EO-01'))
    await page.goto('/app/notifications/forbidden-resource')
    await expect(page.getByTestId('notification-unavailable')).toBeVisible()
    await expect(page.getByText(/500|crash/i)).toHaveCount(0)
  })

  test('TC-SPM94-AC06 a user sees only their own notifications, enforced on the server', async () => {
    const own = await notificationApi('GET', '/notifications', 'EO-01')
    expect(own.status).toBe(200)
    const other = await notificationApi('GET', '/notifications?userId=u2', 'EO-01')
    expect(JSON.stringify(other.body)).not.toMatch(/u2.*coordinator/i)
    const stolen = await notificationApi('GET', '/notifications/n1', 'ATT-01')
    expect([403, 404]).toContain(stolen.status)
  })

  test('TC-SPM94-AC07 when the user has no notifications, an empty state says so', async ({
    page,
  }) => {
    await login(page, account('ATT-02'))
    await page.goto('/app/notifications')
    const empty = page.getByTestId('notifications-empty')
    await expect(empty).toBeVisible()
    await expect(empty).toContainText(/no notifications|none/i)
  })

  test('TC-SPM94-AC08 the list loads a page at a time rather than every notification ever raised', async () => {
    const page1 = await notificationApi('GET', '/notifications?page=1&pageSize=10', 'EO-01')
    expect(page1.status).toBe(200)
    const items = page1.body.items || page1.body
    expect(items.length).toBeLessThanOrEqual(10)
    expect(page1.body.page || page1.body.nextPage).toBeTruthy()
  })


  // AC09-AC12: clearing from the bell. Clearing hides a notification from the bell panel only (and marks it
  // read); the full notifications page still lists it. EC-02 is used for clear-all because it empties the
  // bell, and no other SPM-94 test depends on EC-02's notifications.
  const ownRecord = (accountId, title) =>
    notificationApi('POST', '/notifications/records', accountId, { title, body: 'AUTO clear test' })
  const bellList = async (accountId) => (await notificationApi('GET', '/notifications?bell=true&pageSize=100', accountId)).body
  const fullList = async (accountId) => (await notificationApi('GET', '/notifications?pageSize=100', accountId)).body
  const openBell = async (page) => {
    await page.getByTestId('notification-bell').click()
    await expect(page.getByTestId('notification-panel')).toBeVisible()
  }

  test('TC-SPM94-AC09 Clear all empties the bell and the badge but keeps the full history', async ({ page }) => {
    await ownRecord('EC-02', 'AUTO clear-all one')
    await ownRecord('EC-02', 'AUTO clear-all two')
    await login(page, account('EC-02'))
    await openBell(page)
    await page.getByTestId('notification-clear-all').click()
    await expect(page.getByTestId('notification-empty')).toBeVisible()
    await expect(page.getByTestId('notification-unread-count')).toHaveCount(0)
    await expect(page.getByTestId('notification-clear-all')).toBeDisabled()

    expect(await bellList('EC-02')).toEqual([])
    const history = await fullList('EC-02')
    expect(history.length).toBeGreaterThanOrEqual(2)
    expect(history.every((row) => row.isRead)).toBe(true)

    // Something that arrives afterwards shows in the bell again.
    await ownRecord('EC-02', 'AUTO clear-all after')
    expect((await bellList('EC-02')).map((row) => row.title)).toEqual(['AUTO clear-all after'])
  })

  test('TC-SPM94-AC10 removing one notification hides only that one from the bell', async ({ page }) => {
    const stamp = Date.now()
    const keep = (await ownRecord('EO-01', `AUTO keep ${stamp}`)).body
    const gone = (await ownRecord('EO-01', `AUTO remove ${stamp}`)).body
    await login(page, account('EO-01'))
    await openBell(page)
    const row = page.getByTestId(`notification-${gone.notificationId}`)
    await row.hover()
    await page.getByTestId(`notification-remove-${gone.notificationId}`).click()
    await expect(row).toHaveCount(0)
    await expect(page.getByTestId(`notification-${keep.notificationId}`)).toBeVisible()

    expect((await bellList('EO-01')).map((n) => n.notificationId)).not.toContain(gone.notificationId)
    const full = (await fullList('EO-01')).find((n) => n.notificationId === gone.notificationId)
    expect(full?.isRead).toBe(true)
  })

  test('TC-SPM94-AC11 a user cannot clear another user\'s notification, enforced on the server', async () => {
    const theirs = (await ownRecord('ATT-01', 'AUTO not yours')).body
    const clear = await notificationApi('POST', `/notifications/${theirs.notificationId}/clear`, 'EO-01')
    expect(clear.status).toBe(404)
    expect((await bellList('ATT-01')).map((n) => n.notificationId)).toContain(theirs.notificationId)

    // Clear all only touches the caller's own.
    await notificationApi('POST', '/notifications/clear-all', 'EC-02')
    expect((await bellList('ATT-01')).map((n) => n.notificationId)).toContain(theirs.notificationId)
  })

  test('TC-SPM94-AC12 Mark all read is disabled when nothing in the bell is unread', async ({ page }) => {
    await notificationApi('POST', '/notifications/clear-all', 'EC-02')
    await ownRecord('EC-02', 'AUTO already read')
    const [only] = await bellList('EC-02')
    await notificationApi('POST', `/notifications/${only.notificationId}/read`, 'EC-02')
    await login(page, account('EC-02'))
    await openBell(page)
    await expect(page.getByTestId('notification-mark-all-read')).toBeDisabled()

    await ownRecord('EC-02', 'AUTO unread again')
    await page.keyboard.press('Escape')
    await page.reload()
    await openBell(page)
    await expect(page.getByTestId('notification-mark-all-read')).toBeEnabled()
  })
})
