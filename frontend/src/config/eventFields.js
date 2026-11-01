// Event request fields as people read them, in form order. The server keeps
// the matching lists (EventCreate's fields, CHANGEABLE_FIELDS).
export const FIELD_LABELS = {
  eventName: 'Name',
  purpose: 'Purpose',
  description: 'Description',
  category: 'Category',
  proposedStartAt: 'Start',
  proposedEndAt: 'End',
  expectedAttendance: 'Expected attendance',
  venueRequirements: 'Venue requirements',
  accessibilityNeeds: 'Accessibility needs',
  equipmentRequirements: 'Equipment requirements',
  layoutPreference: 'Layout',
  registrationEnabled: 'Registration',
  registrationOpensAt: 'Registration opens',
  registrationClosesAt: 'Registration closes',
  capacity: 'Capacity',
}

// Only a change request can ask for these (SPM-85), so they are not offered as clarification fields.
const CHANGE_REQUEST_LABELS = { equipmentLines: 'Equipment' }

export const fieldLabel = (field) => FIELD_LABELS[field] || CHANGE_REQUEST_LABELS[field] || field

// SPM-106: the fields a change request can propose (GET /events/changeable-fields lists the same).
export const CHANGEABLE_FIELDS = [
  'eventName', 'description', 'purpose', 'category', 'proposedStartAt', 'proposedEndAt',
  'expectedAttendance', 'layoutPreference', 'accessibilityNeeds', 'equipmentRequirements', 'equipmentLines',
]

// The categories event-service accepts; forms read them from /events/requirement-options and
// fall back to this copy only while it cannot be read.
export const EVENT_CATEGORIES = ['Conference', 'Workshop', 'Networking', 'Meeting']
