import { test, expect } from '@playwright/test'
import { login, logout } from './support/auth.js'
import { account } from './support/test-data.js'
import { venuePeriod } from './support/api-data.js'
import { eventApi } from './support/event.js'
import { approveRequest, createEquipment, createPendingRequest, equipmentApi } from './support/equipment.js'
import { approvedEvent } from './support/venue-request.js'

// The home screen lists the whole team's work, so these tests make their own events and equipment
// instead of relying on seeded rows that other suites review, reserve, or re-verify. Each event is on
// its own random day years ahead, with its own equipment, so neither earlier runs nor stock get in the way.
const run = Date.now()
const fixtures = {}

async function eventWithRequest(label, day, quantity = 1) {
  const period = venuePeriod(day)
  const event = await approvedEvent({
    eventName: `AUTO-SPM58-${label}-${run}`,
    proposedStartAt: period.startsAt,
    proposedEndAt: period.endsAt,
  })
  const equipment = await createEquipment(`AUTO-SPM58-${label}-${run}`, { totalQuantity: 4 })
  const request = await createPendingRequest({
    eventId: event.eventId,
    equipmentId: equipment.equipmentId,
    quantity,
    startsAt: period.startsAt,
    endsAt: period.endsAt,
    technicalRequirements: `AUTO-SPM58-${label}`,
  })
  return { event, request }
}

async function reserve(requestId) {
  await approveRequest(requestId)
  const reserved = await equipmentApi('POST', `/equipment/requests/${requestId}/reserve`, 'TS-01')
  expect(reserved.status, JSON.stringify(reserved.body)).toBe(201)
  return reserved.body
}

test.describe('SPM-58 Technical Support Staff dashboard', () => {
  test.beforeAll(async () => {
    const day = 300 + Math.floor(Math.random() * 30000)

    // AC1: a request awaiting review.
    fixtures.pending = await eventWithRequest('pending', day)

    // AC2 and AC4: a reserved line, then a significant change flags it.
    fixtures.flagged = await eventWithRequest('flagged', day + 2)
    fixtures.flaggedReservation = await reserve(fixtures.flagged.request.requestId)
    const flag = await equipmentApi('POST', '/equipment/reservations/reverification', 'EC-01', {
      eventId: fixtures.flagged.event.eventId,
      reason: 'Attendance doubled',
    })
    expect(flag.status, JSON.stringify(flag.body)).toBe(200)

    // AC3 and AC4: one of two units reserved, one short.
    fixtures.short = await eventWithRequest('short', day + 1, 2)
    const partial = await equipmentApi('POST', `/equipment/requests/${fixtures.short.request.requestId}/partial`, 'TS-01', {
      reservedQuantity: 1,
      reason: 'One unit is in for repair',
    })
    expect(partial.status, JSON.stringify(partial.body)).toBe(200)
  })

  test.afterAll(async () => {
    // A cancelled event is no longer live, so it and its lines leave the home screen.
    for (const item of [fixtures.pending, fixtures.flagged, fixtures.short]) {
      if (item) await eventApi('POST', `/${item.event.eventId}/cancel`, 'EO-01', { reason: 'SPM-58 suite clean-up' })
    }
  })

  test('TC-SPM58-AC01 equipment requests awaiting review show event and date', async ({ page }) => {
    const { event, request } = fixtures.pending
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-section-pending')).toBeVisible()
    const item = page.getByTestId(`tech-pending-${request.requestId}`)
    await expect(item).toBeVisible()
    await expect(item).toContainText(event.eventName)
    await expect(item.getByTestId(`tech-pending-${request.requestId}-date`)).toBeVisible()
  })

  test('TC-SPM58-AC02 reservations flagged for re-verification are shown', async ({ page }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-section-reverification')).toBeVisible()
    const item = page.getByTestId(`tech-reverification-${fixtures.flaggedReservation.reservationId}`)
    await expect(item).toBeVisible()
    await expect(item).toContainText(fixtures.flagged.event.eventName)
    await expect(item).toContainText('Attendance doubled')
  })

  test('TC-SPM58-AC03 unresolved unavailable or partly fulfilled lines are shown', async ({ page }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-section-shortfall')).toBeVisible()
    const item = page.getByTestId(`tech-shortfall-${fixtures.short.request.requestId}`)
    await expect(item).toBeVisible()
    await expect(item).toContainText(fixtures.short.event.eventName)
    await expect(item).toContainText(/partly fulfilled|unavailable|shortfall/i)
  })

  test('TC-SPM58-AC04 upcoming supplied events are soonest first', async ({ page }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId('tech-section-upcoming')).toBeVisible()
    const items = page.getByTestId('tech-upcoming')
    await expect(items).not.toHaveCount(0)
    await expect(items.filter({ hasText: fixtures.flagged.event.eventName })).toHaveCount(1)
    const labels = await items.allTextContents()
    const sooner = labels.findIndex((text) => text.includes(fixtures.short.event.eventName))
    const later = labels.findIndex((text) => text.includes(fixtures.flagged.event.eventName))
    expect(sooner).toBeGreaterThanOrEqual(0)
    expect(sooner).toBeLessThan(later)
    // Awaiting review only: nothing is held for it yet, so it is not being supplied.
    await expect(items.filter({ hasText: fixtures.pending.event.eventName })).toHaveCount(0)
  })

  test('TC-SPM58-AC05 each item opens the work screen', async ({ page }) => {
    await login(page, account('TS-01'))
    const opens = [
      [`tech-pending-${fixtures.pending.request.requestId}`, fixtures.pending.event.eventId],
      [`tech-reverification-${fixtures.flaggedReservation.reservationId}`, fixtures.flagged.event.eventId],
      [`tech-shortfall-${fixtures.short.request.requestId}`, fixtures.short.event.eventId],
    ]
    for (const [testId, eventId] of opens) {
      await page.getByTestId(testId).click()
      await expect(page).toHaveURL(new RegExp(`/app/events/${eventId}/equipment`))
      await page.goto('/app')
    }
    await page.getByTestId('tech-upcoming').filter({ hasText: fixtures.flagged.event.eventName }).click()
    await expect(page).toHaveURL(new RegExp(`/app/events/${fixtures.flagged.event.eventId}/equipment`))
  })

  test('TC-SPM58-AC06 lists obey the same access rules as the work screens', async ({ page }) => {
    await login(page, account('TS-01'))
    await expect(page.getByTestId(`tech-pending-${fixtures.pending.request.requestId}`)).toBeVisible()
    await logout(page)
    await login(page, account('EO-01'))
    await expect(page.getByTestId('tech-section-pending')).toHaveCount(0)
    const denied = await equipmentApi('GET', '/equipment/dashboard', 'EO-01')
    expect(denied.status).toBe(403)
  })

  test('TC-SPM58-AC07 each section has an empty state', async ({ page }) => {
    // The lists are the whole team's, so an empty day is shown with an empty reply.
    await page.route('**/equipment/dashboard', (route) =>
      route.fulfill({ json: { pending: [], reverification: [], shortfalls: [], upcoming: [] } }),
    )
    await login(page, account('TS-02'))
    await expect(page.getByTestId('tech-pending-empty')).toBeVisible()
    await expect(page.getByTestId('tech-reverification-empty')).toBeVisible()
    await expect(page.getByTestId('tech-shortfall-empty')).toBeVisible()
    await expect(page.getByTestId('tech-upcoming-empty')).toBeVisible()
  })
})
