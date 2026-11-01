import { test, expect } from '@playwright/test'
import { login } from './support/auth.js'
import { account } from './support/test-data.js'
import { setReadinessDue } from './support/database.js'
import { eventApi } from './support/event.js'

const EVENT = 'e1'

test.describe('SPM-05 Follow-up pending items of the given request', () => {
  test('TC-SPM05-AC01 readiness table shows category, handler, status, assignment date, and attachments', async ({
    page,
  }) => {
    const list = await eventApi('GET', `/${EVENT}/readiness`, 'EC-01')
    expect(list.status).toBe(200)
    expect(list.body.length).toBeGreaterThan(0)
    const row = list.body[0]
    expect(row.category).toBeTruthy()
    expect(row.handlerName || row.personnel).toBeTruthy()
    expect(row.status).toBeTruthy()
    expect(row.assignedAt).toBeTruthy()
    expect(row.attachments).toBeDefined()

    await login(page, account('EC-01'))
    await page.goto(`/app/events/${EVENT}/readiness`)
    const item = page.getByTestId('readiness-row').first()
    await expect(item).toBeVisible()
    await expect(item.getByTestId('readiness-category')).toBeVisible()
    await expect(item.getByTestId('readiness-handler')).toBeVisible()
    await expect(item.getByTestId('readiness-status')).toBeVisible()
    await expect(item.getByTestId('readiness-assigned-at')).toBeVisible()
    await expect(item.getByTestId('readiness-attachments')).toBeVisible()

    // The personnel are ConnectSphere staff only: no organiser or attendee can be chosen or saved.
    const choices = page.getByTestId('readiness-create-handler').locator('option')
    await expect(choices.filter({ hasText: 'venue@connectsphere.com' })).toHaveCount(1)
    await expect(choices.filter({ hasText: /organiser\d*@connectsphere\.com/ })).toHaveCount(0)
    await expect(choices.filter({ hasText: /attendee\d*@connectsphere\.com/ })).toHaveCount(0)
    for (const handlerId of ['u1', 'u5']) {
      const refused = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', { category: 'venue', handlerId })
      expect(refused.status, handlerId).toBe(422)
    }
  })

  test('TC-SPM05-AC02 the coordinator can update a line-item readiness status', async () => {
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'venue',
      handlerId: 'u3',
      status: 'outstanding',
    })
    expect(created.status).toBe(201)
    const updated = await eventApi(
      'PATCH',
      `/${EVENT}/readiness-items/${created.body.itemId}`,
      'EC-01',
      { status: 'in_progress' },
    )
    expect(updated.status).toBe(200)
    expect(updated.body.status).toMatch(/in_progress|in progress/i)
  })

  test('TC-SPM05-AC03 assigned personnel contact details are shown for follow-up', async ({
    page,
  }) => {
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${EVENT}/readiness`)
    const contact = page.getByTestId('readiness-handler-contact').first()
    await expect(contact).toBeVisible()
    await expect(contact).toContainText(/@|phone|\+65/i)
  })

  test('TC-SPM05-AC04 supporting attachments can be opened', async ({ page }) => {
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${EVENT}/readiness`)
    const link = page.getByTestId('readiness-attachment-link').first()
    await expect(link).toBeVisible()
    const href = await link.getAttribute('href')
    expect(href).toBeTruthy()
  })

  test('TC-SPM05-AC05 a line item can be created, changed, and deleted', async () => {
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'equipment',
      handlerId: 'u4',
      status: 'outstanding',
      note: 'AUTO-SPM05',
    })
    expect(created.status).toBe(201)
    const changed = await eventApi(
      'PATCH',
      `/${EVENT}/readiness-items/${created.body.itemId}`,
      'EC-01',
      { note: 'AUTO-SPM05-edited' },
    )
    expect(changed.status).toBe(200)
    expect(changed.body.note).toMatch(/edited/)
    const removed = await eventApi(
      'DELETE',
      `/${EVENT}/readiness-items/${created.body.itemId}`,
      'EC-01',
    )
    expect([200, 204]).toContain(removed.status)
    const list = await eventApi('GET', `/${EVENT}/readiness`, 'EC-01')
    expect((list.body || []).map((row) => row.itemId)).not.toContain(created.body.itemId)
  })

  test('TC-SPM05-AC06 saving a line item persists the recorded information', async () => {
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'registration',
      handlerId: 'u2',
      status: 'outstanding',
      note: 'AUTO-persist',
    })
    expect(created.status).toBe(201)
    const read = await eventApi(
      'GET',
      `/${EVENT}/readiness-items/${created.body.itemId}`,
      'EC-01',
    )
    expect(read.status).toBe(200)
    expect(read.body.note).toBe('AUTO-persist')
    expect(read.body.category).toBe('registration')
  })

  test('TC-SPM05-AC07 confirming a status requires an explicit confirmation', async ({ page }) => {
    await login(page, account('EC-01'))
    await page.goto(`/app/events/${EVENT}/readiness`)
    await page.getByTestId('readiness-row').first().getByTestId('readiness-confirm-status').click()
    await expect(page.getByTestId('readiness-confirm-dialog')).toBeVisible()
    await page.getByTestId('readiness-confirm-dialog').getByRole('button', { name: /^confirm$/i }).click()
    await expect(page.getByTestId('readiness-row').first()).toContainText(/confirmed|settled/i)
  })

  test('TC-SPM05-AC08 a line item whose due date is near raises an alert', async () => {
    const soon = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString()
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'venue',
      handlerId: 'u3',
      status: 'outstanding',
      dueAt: soon,
    })
    expect(created.status).toBe(201)
    expect(created.body.dueSoon || created.body.alert).toBeTruthy()
    const alerts = await eventApi('GET', `/${EVENT}/readiness?dueSoon=true`, 'EC-01')
    expect(alerts.status).toBe(200)
    expect((alerts.body || []).map((row) => row.itemId)).toContain(created.body.itemId)
  })

  test('TC-SPM05-AC09 an overdue line item is flagged', async () => {
    // A new due date cannot be before today (AC10), so the item is made due later and then moved
    // two days into the past in the database.
    const created = await eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', {
      category: 'equipment',
      handlerId: 'u4',
      status: 'outstanding',
      dueAt: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
    })
    expect(created.status).toBe(201)
    setReadinessDue(created.body.itemId, -2)
    const list = await eventApi('GET', `/${EVENT}/readiness`, 'EC-01')
    const row = (list.body || []).find((item) => item.itemId === created.body.itemId)
    expect(row.overdue).toBe(true)
  })

  test('TC-SPM05-AC10 a new or changed due date cannot be before today (SGT); an existing overdue date stays valid', async () => {
    const day = 24 * 60 * 60 * 1000
    const create = (dueAt) =>
      eventApi('POST', `/${EVENT}/readiness-items`, 'EC-01', { category: 'venue', handlerId: 'u3', status: 'outstanding', dueAt })
    const made = []
    try {
      const past = await create(new Date(Date.now() - 2 * day).toISOString())
      if (past.status === 201) made.push(past.body.itemId)
      expect(past.status).toBe(422)
      expect(JSON.stringify(past.body)).toMatch(/today/i)

      const item = await create(new Date(Date.now() + 3 * day).toISOString())
      expect(item.status).toBe(201)
      made.push(item.body.itemId)
      const moved = await eventApi('PATCH', `/${EVENT}/readiness-items/${item.body.itemId}`, 'EC-01', {
        dueAt: new Date(Date.now() - day).toISOString(),
      })
      expect(moved.status).toBe(422)

      // Once overdue (set in the database, as the app never saves a past date), other edits still save.
      setReadinessDue(item.body.itemId, -1)
      const noted = await eventApi('PATCH', `/${EVENT}/readiness-items/${item.body.itemId}`, 'EC-01', { note: 'Chasing the venue' })
      expect(noted.status, JSON.stringify(noted.body)).toBe(200)
    } finally {
      for (const itemId of made) await eventApi('DELETE', `/${EVENT}/readiness-items/${itemId}`, 'EC-01')
    }
  })
})
