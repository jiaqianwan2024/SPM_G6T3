import { expect } from '@playwright/test'
import { bearer, cachedIdToken } from './auth.js'
import { serviceUrls, venueBookingPayload } from './api-data.js'

// Shares the sign-in cache with authedApi, so a long run renews a token before it expires.
export function venueToken(id) {
  return cachedIdToken(id)
}

export async function venueRequest(method, path, accountId, body) {
  const response = await fetch(`${serviceUrls.venue}${path}`, {
    method,
    headers: {
      ...bearer(await venueToken(accountId)),
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

export async function notificationRequest(path, accountId) {
  const response = await fetch(`${serviceUrls.notification}${path}`, {
    method: 'GET',
    headers: {
      ...bearer(await venueToken(accountId)),
      'Content-Type': 'application/json',
    },
  })
  return { status: response.status, body: await response.json().catch(() => null) }
}

// Frees a booking a test made: an approved one is cancelled, a pending one withdrawn.
export async function releaseBooking(bookingId) {
  const current = await venueRequest('GET', `/venues/bookings/${bookingId}`, 'VS-01')
  if (current.body?.status === 'approved') {
    await venueRequest('POST', `/venues/bookings/${bookingId}/cancel`, 'VS-01')
  } else if (current.body?.status === 'pending') {
    await venueRequest('POST', `/venues/bookings/${bookingId}/withdraw`, 'EC-01')
  }
}

export async function createPendingBooking(accountId, sequence, extras = {}) {
  const result = await venueRequest(
    'POST',
    '/venues/bookings',
    accountId,
    { ...venueBookingPayload(sequence, extras.eventId || 'e1', extras.venueId || 'v1'), ...extras },
  )
  expect(result.status, JSON.stringify(result.body)).toBe(201)
  return result.body
}
