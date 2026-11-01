import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Spec setup the app itself can never produce, written straight to MySQL. Use it only for that, and say
// why at the call site:
// - SPM-73: an event can be completed only after its end time has passed, but the app never accepts a
//   past date, so a confirmed event is moved into the past (moveIntoPast).
// - SPM-70 AC5: an event can be rejected only while under review, and the app books a venue or reserves
//   equipment only once it is approved for planning, so an event holding both is put back under review
//   (setEventStatus) to check that rejecting releases them.
// - SPM-5 AC9 and AC10: a new due date cannot be before today, so an overdue line item is made by
//   creating it due later and then moving its due date into the past (setReadinessDue).

const COMPOSE_FILE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../infra/docker-compose.yml')

function sql(statements) {
  // The SQL goes in as an argument to sh, so neither the host shell nor sh has to quote it.
  try {
    execFileSync(
      'docker',
      ['compose', '-f', COMPOSE_FILE, 'exec', '-T', 'mysql', 'sh', '-c', 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "$1"', 'sh', statements],
      { stdio: ['ignore', 'ignore', 'pipe'] },
    )
  } catch (error) {
    // MySQL warns about the password on the command line; keep only the real error.
    const detail = String(error.stderr || '').split('\n').filter((line) => line && !line.includes('[Warning]')).join(' ')
    throw new Error(`The database refused the test setup: ${detail || error.message}`)
  }
}

function eventIdOf(eventId) {
  if (!/^[\w-]+$/.test(eventId)) throw new Error(`Not an event id: ${eventId}`)
  return eventId
}

// The event now runs 10:00 to 12:00 Singapore time (02:00 to 04:00 UTC) on a past day of its own, with its
// venue bookings and equipment reservations shifted with it. The database refuses two confirmed bookings of
// one venue at overlapping times, so every moved event needs a different day, across reruns too. One
// transaction, so a refusal leaves the event as it was.
export function moveIntoPast(eventId, daysAgo = 2 + Math.floor(Math.random() * 100_000)) {
  sql(`
    start transaction;
    set @id = '${eventIdOf(eventId)}';
    set @start = timestamp(date_sub(utc_date(), interval ${Number(daysAgo)} day), '02:00:00');
    select timestampdiff(second, @start, proposed_start_at) into @shift from event.events where event_id = @id;
    update event.events
      set proposed_start_at = proposed_start_at - interval @shift second,
          proposed_end_at = proposed_end_at - interval @shift second
      where event_id = @id;
    update venue.venue_bookings
      set starts_at = starts_at - interval @shift second, ends_at = ends_at - interval @shift second,
          setup_starts_at = setup_starts_at - interval @shift second,
          teardown_ends_at = teardown_ends_at - interval @shift second
      where event_id = @id;
    update equipment.equipment_reservations
      set starts_at = starts_at - interval @shift second, ends_at = ends_at - interval @shift second
      where event_id = @id;
    commit;
  `)
}

export function setEventStatus(eventId, status) {
  if (!/^[a-z ]+$/.test(status)) throw new Error(`Not an event status: ${status}`)
  sql(`update event.events set status = '${status}' where event_id = '${eventIdOf(eventId)}';`)
}

export function setReadinessDue(itemId, daysFromNow) {
  sql(`update event.event_readiness_items set due_at = utc_timestamp() + interval ${Number(daysFromNow)} day
    where item_id = '${eventIdOf(itemId)}';`)
}
