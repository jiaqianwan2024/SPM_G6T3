import { test, expect } from '@playwright/test'
import { serviceUrls } from './support/api-data.js'
import { authedApi, login } from './support/auth.js'
import { account } from './support/test-data.js'
import { THEATRE_EVENT, approvedEvent } from './support/venue-request.js'

// SPM-127: a signed-in attendee sees only public event pages and their own
// registrations. The seeded registrations are read, never changed: ATT-01 (u5)
// holds r-att-e1 (e1, confirmed) and r-att-e8 (e8, "Cancelled Briefing");
// ATT-02 holds none. Each test that needs an unconfirmed event makes its own.

const REFUSAL = 'Attendees can open only confirmed event pages and their own registrations.'
// On the full event record, never on the attendee's public page.
const INTERNAL_FIELDS = ['internalNotes', 'coordinatorId', 'organiserId', 'organisationId', 'equipmentLines', 'venueRequirements']

const event = (path) => `${serviceUrls.event}/events${path}`

test.describe('SPM-127 Restrict attendees to public event information', () => {
  test('TC-SPM127-AC01 an attendee opens confirmed event pages and their own registrations', async () => {
    const confirmed = await authedApi('GET', event('/e1/attendee-card'), 'ATT-01')
    const mine = await authedApi('GET', `${serviceUrls.registration}/registrations/r-att-e1`, 'ATT-01')
    // Cancelled after they registered: still theirs, so still opens (boundary).
    const registeredCancelled = await authedApi('GET', event('/e8/attendee-card'), 'ATT-01')

    expect([confirmed.status, confirmed.body.status]).toEqual([200, 'confirmed'])
    expect([mine.status, mine.body.userId]).toEqual([200, 'u5'])
    expect([registeredCancelled.status, registeredCancelled.body.status]).toEqual([200, 'cancelled'])
  })

  test('TC-SPM127-AC01b an event that is not confirmed, or another attendee\'s registration, is refused', async () => {
    const planning = await approvedEvent(THEATRE_EVENT)

    const unconfirmed = await authedApi('GET', event(`/${planning.eventId}/attendee-card`), 'ATT-01')
    const notTheirs = await authedApi('GET', event('/e8/attendee-card'), 'ATT-02')
    const someoneElses = await authedApi('GET', `${serviceUrls.registration}/registrations/r-att-e1`, 'ATT-02')

    expect([unconfirmed.status, unconfirmed.body.detail]).toEqual([403, REFUSAL])
    expect([notTheirs.status, notTheirs.body.detail]).toEqual([403, REFUSAL])
    expect(someoneElses.status).toBe(403)
  })

  test('TC-SPM127-AC01c the public pages open in the browser', async ({ page }) => {
    await login(page, account('ATT-01'))

    await page.goto('/app/registrations/r-att-e8')
    await expect(page.getByRole('heading', { name: 'Cancelled Briefing' })).toBeVisible()

    await page.goto('/app/browse/e8')
    await expect(page.getByRole('heading', { name: 'Cancelled Briefing' })).toBeVisible()
  })

  test('TC-SPM127-AC02 internal details never reach an attendee', async () => {
    const card = await authedApi('GET', event('/e1/attendee-card'), 'ATT-01')
    const places = await authedApi('GET', `${serviceUrls.registration}/registrations?eventId=e1`, 'ATT-01')
    const refused = {
      'the full event record': event('/e1'),
      'the list of events': event(''),
      'the list of all events': event('/all'),
      'the list of confirmed events': event('/confirmed'),
      'the activity log': event('/e1/activity-log'),
      'clarification threads': event('/e1/clarifications'),
      'internal staff notes': event('/e1/internal-notes'),
      'other people in the user directory': `${serviceUrls.user}/users`,
    }

    expect(card.status).toBe(200)
    expect(INTERNAL_FIELDS.filter((field) => field in card.body)).toEqual([])
    expect([places.status, places.body.attendees]).toEqual([200, []])
    for (const [name, url] of Object.entries(refused)) {
      expect((await authedApi('GET', url, 'ATT-01')).status, name).toBe(403)
    }
  })

  test('TC-SPM127-AC03 staff-only and organiser-only pages are 403 for an attendee', async () => {
    const staffOrOrganiser = [
      [event('/e1'), REFUSAL],
      [event('/drafts/mine'), /organisers/],
      [event('/queue'), /permission/],
      [`${serviceUrls.venue}/venues`, /permission/],
      [`${serviceUrls.equipment}/equipment`, REFUSAL],
      [`${serviceUrls.equipment}/equipment/reservations/summary?eventId=e1`, REFUSAL],
    ]

    for (const [url, detail] of staffOrOrganiser) {
      const response = await authedApi('GET', url, 'ATT-01')
      expect(response.status, url).toBe(403)
      if (typeof detail === 'string') expect(response.body.detail, url).toBe(detail)
      else expect(response.body.detail, url).toMatch(detail)
    }
  })

  test('TC-SPM127-AC03b an attendee who opens a staff event page is told it is not available', async ({ page }) => {
    await login(page, account('ATT-01'))

    await page.goto('/app/events/e1')

    await expect(page.getByText('This event is no longer available to you.')).toBeVisible()
    await expect(page.getByText('Internal notes')).toHaveCount(0)
  })

  test('TC-SPM127-AC03c a notification about an event takes an attendee to its public page', async ({ page }) => {
    await page.goto('/')
    const targets = await page.evaluate(async () => {
      const { notificationTarget } = await import('/src/features/notifications/target.js')
      return {
        attendee: notificationTarget({ eventId: 'e8', link: '/app/events/e8' }, 'attendee'),
        attendeeOldNotice: notificationTarget({ eventId: 'e8' }, 'attendee'),
        attendeeOtherLink: notificationTarget({ eventId: 'e8', link: '/app/registrations/r-att-e8' }, 'attendee'),
        staff: notificationTarget({ eventId: 'e8', link: '/app/events/e8' }, 'coordinator'),
      }
    })

    expect(targets).toEqual({
      attendee: '/app/browse/e8',
      attendeeOldNotice: '/app/browse/e8',
      attendeeOtherLink: '/app/registrations/r-att-e8',
      staff: '/app/events/e8',
    })
  })
})
