import { expect } from '@playwright/test'
import { account } from './test-data.js'
import { firebaseIdToken, bearer } from './auth.js'
import { serviceUrls } from './api-data.js'
import { confirm, events, readyToConfirm } from './confirmation.js'

const DAY = 86400000
const tokens = {}

async function token(id) {
  if (!tokens[id]) tokens[id] = await firebaseIdToken(null, account(id))
  return tokens[id]
}

export async function registrationApi(method, path, accountId, body) {
  const response = await fetch(`${serviceUrls.registration}${path}`, {
    method,
    headers: {
      ...bearer(await token(accountId)),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

export async function notificationApi(method, path, accountId, body) {
  const response = await fetch(`${serviceUrls.notification}${path}`, {
    method,
    headers: {
      ...bearer(await token(accountId)),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

// A confirmed event of its own with registration open, created through the app rather than the
// seed, so filling and freeing its places changes no seeded event. Hand it to releaseEvents once
// the spec is done, or it stays on every attendee's screens.
export async function openEvent(label, { capacity = 5, opensAt = Date.now() - DAY, closesAt = Date.now() + 60 * DAY } = {}) {
  const event = await readyToConfirm(label, {
    registrationEnabled: true,
    capacity,
    registrationOpensAt: new Date(opensAt).toISOString(),
    registrationClosesAt: new Date(closesAt).toISOString(),
  })
  const confirmed = await confirm(event)
  expect(confirmed.status, JSON.stringify(confirmed.body)).toBe(200)
  return event
}

// Withdraw the attendees' registrations on these events, then cancel the events, so they leave
// Browse Events and the attendee home and the attendee accounts start the next spec empty-handed.
export async function releaseEvents(eventIds) {
  const ids = new Set(eventIds)
  for (const accountId of ['ATT-01', 'ATT-02']) {
    const mine = await registrationApi('GET', '/registrations/mine', accountId)
    for (const row of mine.body || []) {
      if (!ids.has(row.eventId) || row.status !== 'registered') continue
      const withdrawn = await registrationApi('POST', `/registrations/${row.attendeeRegistrationId}/withdraw`, accountId)
      expect(withdrawn.status, JSON.stringify(withdrawn.body)).toBe(200)
    }
  }
  for (const eventId of ids) {
    const cancelled = await events('POST', `/${eventId}/cancel`, 'EC-01', { reason: 'Automated test finished.' })
    expect(cancelled.status, JSON.stringify(cancelled.body)).toBe(200)
  }
}

// The signed-in attendee registers themselves; the email is left out, so the server fills in
// the account's own.
export function guestRegistration(eventId, label = 'AUTO') {
  return { eventId, name: `${label} Guest` }
}
