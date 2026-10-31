// Plain-language event status labels. Anything not listed shows as stored.
const LABELS = {
  // SPM-71 AC6: a confirmed event whose date, time, attendance, layout,
  // accessibility or equipment changed no longer reads as fully confirmed.
  reconsidering: 'Arrangements being reconsidered',
  // SPM-120: waiting on a Safety Officer, then on the coordinator to confirm (SPM-72).
  // SPM-121 AC5: the organiser can tell the event is waiting on the review.
  'safety review': 'Waiting on safety review',
  'safety approved': 'Safety approved',
}

// The organiser's five plain-language stages. My Events filters by these and the
// dashboard groups by them, so both screens use the same words. The status itself
// stays visible as the pill on each event.
export const EVENT_STAGES = [
  { key: 'drafts', label: 'Drafts', statuses: ['draft'] },
  { key: 'in-review', label: 'In review', statuses: ['submitted', 'under review', 'changes requested'] },
  {
    key: 'in-preparation',
    label: 'In preparation',
    statuses: ['approved', 'planning', 'safety review', 'safety approved', 'preparing', 'prepared'],
  },
  { key: 'confirmed', label: 'Confirmed', statuses: ['confirmed', 'reconsidering'] },
  { key: 'closed', label: 'Closed', statuses: ['completed', 'rejected', 'cancelled'] },
]

// SPM-121 AC5: an event back in planning after its safety review says why.
// One waiting on the review already reads so from its status.
const SAFETY_NOTES = {
  changes_requested: 'Safety changes requested',
  rejected: 'Safety review rejected',
}

export function eventSafetyNote(event) {
  if (!SAFETY_SUBMITTABLE_STATUSES.includes(event.status)) return ''
  return SAFETY_NOTES[event.safetyReviewStatus] || ''
}

export const eventStatusLabel = (status) => LABELS[status] || String(status || 'Unknown')

// Colour tone for a status pill: success | warning | danger | info | neutral.
const TONES = {
  confirmed: 'success',
  completed: 'success',
  'safety approved': 'success',
  'changes requested': 'warning',
  reconsidering: 'warning',
  'safety review': 'warning',
  rejected: 'danger',
  cancelled: 'danger',
  'under review': 'info',
  planning: 'info',
  approved: 'info',
  preparing: 'info',
  prepared: 'info',
}

export const eventStatusTone = (status) => TONES[status] || 'neutral'

// SPM-71 AC7: completed, cancelled and rejected events can't be edited. A draft
// is the organiser's to edit, and a discarded draft is gone.
export const LOCKED_EVENT_STATUSES = ['completed', 'cancelled', 'rejected', 'draft', 'discarded']

// SPM-70 AC2: the reasons a coordinator can reject a request for (the backend accepts only these).
export const REJECTION_REASONS = [
  'no suitable venue available',
  'insufficient equipment',
  'insufficient notice',
  'outside ConnectSphere services',
]

// SPM-90: registration is set up from planning until the event is confirmed
// ("approved" is planning's older name; a reconsidering event is still confirmed).
export const REGISTRATION_SETUP_STATUSES = [
  'approved', 'planning', 'safety review', 'safety approved', 'preparing', 'prepared', 'confirmed', 'reconsidering',
]

// SPM-106: an organiser can request a change while the event is under review,
// approved, in planning, or confirmed. Drafts are edited directly.
export const CHANGE_REQUEST_STATUSES = [
  'under review', 'changes requested', 'approved', 'planning', 'safety review', 'safety approved', 'preparing',
  'prepared', 'confirmed', 'reconsidering',
]

// SPM-72: the coordinator's path to Confirmed — planning, the safety review, then confirm.
export const CONFIRMATION_PATH_STATUSES = ['approved', 'planning', 'safety review', 'safety approved']

// SPM-120: the assigned coordinator submits a planning event for a safety
// review once its venue and equipment are confirmed ("approved" is planning's older name).
export const SAFETY_SUBMITTABLE_STATUSES = ['approved', 'planning']

// An assigned request under review, or waiting on the organiser. Its assigned
// coordinator can raise clarifications on it (SPM-68) or approve it (SPM-69).
export const IN_REVIEW_EVENT_STATUSES = ['under review', 'changes requested']
