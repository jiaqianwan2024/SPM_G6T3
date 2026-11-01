// Unique, stable-per-instance DOM ids for label/aria wiring (Vue 3.4 has no useId).
let counter = 0
export const uid = (prefix = 'ui') => `${prefix}-${++counter}`
