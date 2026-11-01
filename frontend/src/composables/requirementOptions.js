import { reactive } from 'vue'
import { getRequirementOptions } from '../api/eventService.js'
import { EVENT_CATEGORIES } from '../config/eventFields.js'

// SPM-80: the choices for an event's layout, facilities, accessibility and category,
// as event-service publishes them: what the active venues offer, and the categories
// it accepts. These stand in until it answers, or while it cannot be read.
const FALLBACK = {
  layouts: ['Theatre', 'Boardroom', 'Classroom', 'Banquet', 'No preference'],
  facilities: ['Projector', 'PA system', 'Video-conferencing', 'Stage'],
  accessibility: ['Wheelchair accessible', 'Accessible restrooms nearby'],
  categories: EVENT_CATEGORIES,
}

export function useRequirementOptions() {
  const options = reactive({ ...FALLBACK })
  const ready = getRequirementOptions()
    .then(({ data }) => {
      for (const key of Object.keys(FALLBACK)) {
        if (data?.[key]?.length) options[key] = data[key]
      }
    })
    .catch(() => {})
  return { options, ready }
}
