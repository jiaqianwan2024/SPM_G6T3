// The venues a screen's venue filter offers: the active ones, in the order every
// venue list uses (the Venue Calendar's too), then a retired venue only while
// the screen still shows something at it, or it is the one already chosen. Old
// requests and blocks stay filterable without listing every venue ever retired.
export function venueFilterOptions(venues, idsShown = [], selectedId = '') {
  const shown = new Set([...idsShown, selectedId].filter(Boolean))
  const active = venues.filter((venue) => venue.isActive !== false)
  const retired = venues.filter((venue) => venue.isActive === false && shown.has(venue.venueId))
  return [
    ...active.map((venue) => ({ venueId: venue.venueId, name: venue.name })),
    ...retired.map((venue) => ({ venueId: venue.venueId, name: `${venue.name} (retired)` }))
  ]
}
