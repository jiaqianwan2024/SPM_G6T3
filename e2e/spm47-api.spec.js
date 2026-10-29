import { test, expect } from '@playwright/test'
import { eventApi, createDraftEvent } from './support/event.js'

// SPM-47: an organiser sees and opens only their own client organisation's events.
// Seeded events are read, never changed: org-1 (Apex Partners) has e1 by EO-01 (u1)
// and e7 "Colleague Town Hall" by EO-03 (u8); org-2 (Beacon Media) has e5
// "Beacon Q4 Showcase" by EO-02 (u7). The draft check makes, then discards, its own draft.

const REFUSAL = "You can only open your own organisation's events."

const ids = (response) => {
  expect(response.status, JSON.stringify(response.body)).toBe(200)
  return response.body.map((event) => event.eventId)
}

test.describe('SPM-47 Multi-Tenant Event Access Restriction (API)', () => {
  test('TC-SPM47-AC01 the overview lists only the organisation\'s requests, drafts and past records', async () => {
    // The whole organisation's list is slow on a database earlier runs filled with test events.
    test.slow()
    const draft = await createDraftEvent('EO-01', `AUTO-SPM47-DRAFT-${Date.now()}`)
    try {
      const mine = ids(await eventApi('GET', '/mine', 'EO-01'))
      const colleague = ids(await eventApi('GET', '/mine', 'EO-03'))
      const otherOrganisation = ids(await eventApi('GET', '/mine', 'EO-02'))

      expect(mine).toEqual(expect.arrayContaining(['e1', 'e7', draft.eventId]))
      expect(mine).not.toContain('e5')
      // A draft stays with the organiser writing it, so a colleague's list leaves it out.
      expect(colleague).not.toContain(draft.eventId)
      expect(otherOrganisation).toContain('e5')
      expect(otherOrganisation).not.toContain('e1')
      expect(otherOrganisation).not.toContain(draft.eventId)
    } finally {
      await eventApi('DELETE', `/${draft.eventId}`, 'EO-01')
    }
  })

  test('TC-SPM47-AC02 every organiser in the organisation sees its events', async () => {
    // The whole organisation's list is slow on a database earlier runs filled with test events.
    test.slow()
    const colleague = ids(await eventApi('GET', '/mine', 'EO-03'))
    const owner = ids(await eventApi('GET', '/mine', 'EO-01'))

    expect(colleague).toEqual(expect.arrayContaining(['e1', 'e7']))
    expect(owner).toEqual(expect.arrayContaining(['e1', 'e7']))
  })

  test('TC-SPM47-AC03 another organisation\'s event URL is rejected with 403', async () => {
    for (const path of ['/e5', '/e5/activity-log', '/e5/readiness']) {
      const refused = await eventApi('GET', path, 'EO-01')
      expect([refused.status, refused.body.detail], path).toEqual([403, REFUSAL])
    }
    const theirsForMe = await eventApi('GET', '/e1', 'EO-02')
    const listed = ids(await eventApi('GET', '', 'EO-01'))

    expect([theirsForMe.status, theirsForMe.body.detail]).toEqual([403, REFUSAL])
    expect(JSON.stringify(theirsForMe.body)).not.toContain('AI in Events Summit')
    expect(listed).not.toContain('e5')
  })

  test('TC-SPM47-AC04 organisers open their own organisation\'s events and staff open any event', async () => {
    const own = await eventApi('GET', '/e1', 'EO-01')
    const colleagues = await eventApi('GET', '/e7', 'EO-01')
    const theirs = await eventApi('GET', '/e5', 'EO-02')

    expect([own.status, own.body.eventName]).toEqual([200, 'AI in Events Summit'])
    expect([colleagues.status, colleagues.body.eventName]).toEqual([200, 'Colleague Town Hall'])
    expect([theirs.status, theirs.body.eventName]).toEqual([200, 'Beacon Q4 Showcase'])
    for (const staff of ['EC-01', 'ECL-01', 'VS-01', 'TS-01', 'SO-01']) {
      const opened = await eventApi('GET', '/e5', staff)
      expect([opened.status, opened.body.eventId], staff).toEqual([200, 'e5'])
    }
    expect(ids(await eventApi('GET', '', 'ECL-01'))).toEqual(expect.arrayContaining(['e1', 'e5', 'e7']))
  })
})
