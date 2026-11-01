# Acceptance-Criteria Gaps (stories marked Done in Jira)

Audit of every Jira story with status **Done** against this repository, first run on branch `final_tests`
at `7846f93` (1 Nov 2026). It was re-checked after the team's PRs #116–#119 (`c720d40`), with a round of
fixes in the working tree on top. **Those fixes are not committed yet.** A gap was confirmed by reading
the code, and where marked **LIVE**, by calling the running services. A passing e2e test was not taken
as proof on its own (see [Test-suite caveats](#test-suite-caveats)).

When you close a gap, move it to [Fixed](#fixed) or delete it, and update [traceability.md](traceability.md).
Out of scope: SPM-56, SPM-123, SPM-124 (In Progress) and the scrapped or deprecated stories.

## Status at a glance

| Area | Stories | Status |
|---|---|---|
| Attendee registration only worked for seeded events | SPM-11 (and SPM-12, 59, 89, 90, 91, 92, 105) | Fixed |
| No attendee registration UI | SPM-11 AC2, AC3, AC5, AC6, AC8 | Fixed |
| Registration notices, last-place race, period in the refusal | SPM-11 AC3, AC7, AC8, AC10 | Fixed |
| Change-request impact assessment | SPM-85 AC2–AC5 | Fixed upstream (PR #116) |
| Reschedule UI | SPM-87 AC1, AC2, AC4, AC7 | Fixed |
| Technical-support and coordinator equipment actions | SPM-77 AC1, AC2, AC5, AC6; SPM-78 AC1–AC4; SPM-86 AC7, AC10 | Fixed |
| Drafts visible to staff | SPM-79 AC6 | Fixed |
| Category, purpose and attendance not required on submit | SPM-14 AC1, SPM-82 AC1 | Fixed |
| Out-of-service shortfall not notified | SPM-75 AC6 | Fixed |
| Near-due readiness items not alerted | SPM-5 AC8 | Fixed |
| No notice when a hold expires | SPM-93 AC4, SPM-116 AC5 | Fixed |
| Lead and Safety Officer cannot use the venue calendar | SPM-108 AC7 | Fixed |
| Release reason skipped for a reconsidered event | SPM-78 AC4 | Fixed |
| Submitted event shows no change-request route | SPM-14 AC4, SPM-82 AC4 | Fixed in the UI (story conflict, see below) |
| C4 model: dynamic view and design notes | SPM-49 AC4, AC5 | Fixed; AC6 partly open |
| Safety handoff 503 for its senders | SPM-120 (bug) | Fixed |
| Upcoming equipment queue too slow (12–13 s) | SPM-4 (performance) | Fixed |
| Every request paid ~200 ms building an HTTP client to check the caller | All screens (performance) | Fixed |
| Coordinator dashboard makes one request per event per section | SPM-55 (performance) | **Open** |
| Notifications that only go to the stub email | SPM-69 AC3, SPM-68 AC2, SPM-63 AC5, AC8, SPM-115, SPM-3 AC7 | **Deferred** until real email is set up |
| SPM-93 rules bypassed by `/notifications/records` | SPM-93 AC5, AC6 | **Open** (story conflict) |
| Specs that need rewriting; seed drift | spm93, spm95; seeded e1/e2 | **Open** (test suite) |

## Still open

### Deferred: notifications that only reach the stub email

`POST /notifications` (`services/notification-service/app/services/notifier.py`, `send_email`) only
`print()`s. These flows notify only through it, so nobody is told. They are deferred on purpose until a
real email connection is confirmed:

| AC | Where |
|---|---|
| SPM-69 AC3: organiser told of the approval | `event_service.py` `_notify_approval` |
| SPM-68 AC2: organiser told a clarification was raised | `event_service.py` `raise_clarification` |
| SPM-63 AC5, AC8: Venue Staff told of a new or withdrawn booking request | `venue-service/app/routers/venue.py` via `notify_venue_staff` |
| SPM-115 and SPM-93 AC4: Venue Staff told of a replacement request | `venue.py` `request_replacement` |
| SPM-3 AC7: the "fully reserved" notice | `equipment_service.py` `_notify_when_fully_reserved`. Per-line `equipment.reserved` does reach the coordinator in the app |

If email is not coming, the quick fix is to also publish each of these through `/notifications/publish`
with a registered trigger, as the other flows already do.

### SPM-93 AC5 and AC6 hold on only one of three write paths

`/notifications/publish` drops the actor, never repeats an occurrence, and keeps staff-only triggers
from attendees. `/notifications/records` and `/records/batch` do none of that. They carry
assignment, confirmation, change-request decisions, registration-setting changes, attendee change notices,
safety handoff and claim notices, and venue-service's notices. Moving them all onto `/publish` is the
fix. But SPM-11 AC3 and SPM-12 AC6 require the attendee to be told about their *own* registration or
withdrawal, which SPM-93 AC5 forbids, so settle that conflict in Jira first.

### Performance: per-event requests and per-call HTTP clients

- **SPM-55 dashboard.** Each section asks once per assigned event (`getConfirmation`, `getChangeRequests`,
  `getEventReservations` in `CoordinatorHome.vue`). It shows a section's results only once every request
  has answered. On a database where test runs have left a coordinator with 276 events on the arrangement path,
  that takes about 30 s even after the fixes below. A batch route on event-service, or showing each event as
  its own answer arrives, would fix it.
- **Service-to-service calls.** `resolve_caller` now shares one TLS context, which takes about 200 ms off every
  request. The other per-call `httpx.Client(...)` and `httpx.get(...)` in the orchestration clients still each
  rebuild one (about 200 ms on Windows). Pass `verify=` a shared context there too, or share the client.

### SPM-49 AC6: the C3 component boxes are not redrawn

The C4 file now has a dynamic view and a design note on every page (see Fixed). The C3 boxes still show the
7 Oct components. The event-service note names what was added since (reschedule, safety handoff, impact
assessment, reminders), but the boxes themselves should be updated.

### Test suite

- **spm93 and spm95 need rewriting.** They call routes that were never built: `/notifications/recipients`,
  `/notifications/triggers`, `/notifications/reminders/run`, `/notifications/reminders/config`, and
  `trigger=`, `eventId=` and `actor=` filters on the inbox. The behaviour is covered by unit tests
  (`services/notification-service/tests/unit/test_notification_publish.py`,
  `services/event-service/tests/unit/test_event_reminders.py`). The e2e specs should drive real flows,
  for example "assign, then read the inbox", and `POST /events/reminders/run`.
- **Seed drift.** `scripts/seed.py` only inserts into empty tables, and many specs change the seeded events
  (e1 and e2 are seeded `confirmed` and end up `reconsidering`, bookings move into 2027, and e8 ages into the past).
  Specs that read seeded e1, e2 or e8 (spm12, spm59, spm73, spm91, spm106 AC10, spm108, spm127 and others) then fail
  without any code fault. Before trusting a run, reset the database: `cd infra && docker compose down -v &&
  docker compose up -d && cd .. && python scripts/migrate.py`. This wipes local data. The lasting fix is for
  those specs to build their own events, as spm11, spm55 and spm86 AC06 now do with `e2e/support/confirmation.js`.

## Fixed

Each fix comes with unit tests that keep the 100% coverage gate.

- **SPM-11, registration window.** `RegistrationService.register` creates the event's `registration_windows`
  row the first time someone registers, and refreshes it from event-service's record each time
  (`registration-service/app/services/registration_service.py`, `_lock_window`). Before this, only
  `seed.py` created those rows, so registering for an event confirmed in the app returned 409.
- **SPM-11 AC8, last-place race.** The window row is locked with `SELECT ... FOR UPDATE`
  (`RegistrationWindowDAO.get_for_event(lock=True)`) while the places are counted. The transaction that first
  looks for the row is ended before the lock is taken. Under MySQL's REPEATABLE READ, a count in that same
  transaction would not see a registration committed while it waited, and both attendees got the last place
  (reproduced live in 1 of 5 runs). **LIVE:** 10 of 10 runs now give exactly one 201 and one "full" 409.
- **SPM-11 AC3 and AC10, notices.** The attendee gets an in-app `registration.confirmed` notice naming the event,
  its date, time and venue. Taking the last place calls the new `POST /events/{id}/capacity-notice`.
  Event-service re-checks the count itself and publishes `registration.full` to the organiser and the
  coordinator, once per capacity value.
- **SPM-11 AC7.** A refusal outside the period states the period in SGT.
- **SPM-11 UI.** The attendee's public event page (`frontend/src/features/browse-events/BrowseEvent.vue`,
  `/app/browse/:id`) has the registration form with inline validation, the "you are registered" panel (also
  shown for an existing registration), and the full notice. Register on the list opens the form straight away. The
  staff page `/app/events/:id` stays closed to attendees (SPM-127). spm11 now opens `/app/browse/...`.
- **SPM-87, reschedule UI.** `frontend/src/features/event-detail/RescheduleEventDialog.vue` opens from
  Reschedule on the event page, for the assigned coordinator. It previews as the times change (venue
  free and suitable, equipment, registration close), names unavailable venues with Reschedule anyway or
  Abandon, and applies with a reason. Everyone who can open the event sees "This event was rescheduled from
  … to …" from the activity log (`event-rescheduled`).
- **SPM-77, SPM-78, SPM-86, equipment UI.**
  - Technical support (`RequestAvailability.vue`, also on the now-real Reservations tab) can:
    partly fulfil a line, suggest an alternative type when marking a line unavailable, mark the whole review
    complete, and change the quantity of, release (with a reason), or re-confirm each held reservation.
  - The coordinator (`EventEquipment.vue`) can accept a shortfall, or amend the line and send it back.
- **SPM-79 AC6.** `require_submitted_for_staff` (`event_service.py`) returns 404 to every non-organiser for a
  draft or discarded event, on the event record and its activity log.
- **SPM-14 AC1 and SPM-82 AC1.**
  - `EventCreate` requires a non-blank category and purpose, and the intake no longer defaults a missing attendance
    to 1. So a submit lists every missing field in one 422, and stored-draft submits check the same fields.
  - The form requires them too, and lists what is still needed by the submit button (`submit-missing-fields`).
  - A draft's event page has Submit request, which confirms with the event's name and reference (`submit-confirmation`).
- **SPM-14 AC4 and SPM-82 AC4.** A submitted event shows the change-request route, disabled, with a note that it
  opens once a coordinator is reviewing the request (`EventChangeRequests.vue`). SPM-106's statuses are unchanged.
- **SPM-75 AC6.** Acknowledging an out-of-service shortfall publishes `equipment.out_of_service` to each affected
  event's coordinator (`equipment_service.py`, `_notify_short_events`).
- **SPM-5 AC8 and SPM-93 AC4.** The daily reminder run (`event-service/app/services/reminders.py`) also:
  - alerts the coordinator (or the Lead, if nobody is assigned) about readiness items due within 3 days
    (`readiness.due_soon`, once per item and due date);
  - announces holds that expired in the last two days (`hold.expired`, read from the new
    `GET /internal/venues/holds/expired`).
- **SPM-108 AC7.** The Coordinator Lead and the Safety Officer have a Venue Calendar tab, and may read the venue
  list it picks from (`CATALOGUE_READER_ROLES`).
- **SPM-78 AC4.** A release needs a reason for a `confirmed` or `reconsidering` event, or when the event cannot
  be read for a signed-in caller. The coordinator and organiser are told in both cases.
- **SPM-49 AC4 and AC5.** `docs/c4-model.drawio` has a new page, "Dynamic: request to confirmation", tracing
  submit → assign → approve → venue request and approval → equipment → safety handoff and review → confirm, and a
  design-decision note on every page.
- **Safety handoff (SPM-120).** The handoff now reads venue bookings and equipment rows with the service key
  (`handoff_arrangements`, plus the new `GET /internal/venues/bookings`). Before this, venue-service refused
  Tech Support and equipment-service refused Venue Staff, so both senders got 503.
- **SPM-4 speed.** The upcoming queue names every event's venue in one call
  (`GET /internal/venues/bookings/public-summaries`) rather than one call per event.
  `GET /equipment/requests` takes an `eventId` filter, so event reads no longer pull the whole table.
  **LIVE:** 56 rows in 1.8 s, down from 34 rows in 12–13 s.
- **Request speed across the app.** `shared/auth/roles.py` hands every `httpx.Client` one TLS context made at
  import. Before this, each request paid about 200 ms rebuilding the trust store just to check the caller. The
  confirmation check also reads bookings, requests and reservations side by side. **LIVE:** a confirmation check
  went from 2.1 s to 0.7 s.
- **Navigation.** Tech Support's unbuilt "My Assignments" and "Maintenance Status" tabs are gone, and "Reservations"
  is the real view (`e2e/support/test-data.js` updated).
- **Specs corrected to match the code and Jira:**
  - spm11: AC08 and AC10 now use an event of their own, so they really test the race and the full notice.
  - spm14 and spm82: drafts are made with `/drafts`, then submitted once.
  - spm15 AC07: compares against the status label.
  - spm55: rewritten against the current dashboard, with its own data.
  - spm75 AC06: checks the coordinator is told.
  - spm79 AC05: the confirm dialog keeps the form.
  - spm80 AC01: waits for the save.
  - spm86 AC06: uses its own event.
  - spm88 AC08: waits for the asynchronous notice.
  - spm89 AC05 and spm105 AC04: attendees get counts only, never names.
  - spm94 AC08: pages do not overlap.
  - spm119: rejects with the SPM-70 reason list.
  - spm121: checks attendee visibility through the routes attendees may use.
  - spm04 EXTRA05: FullCalendar 7 has no plain `.fc` class.
  - spm87 AC08: uses its own event whose registration closes after the new start.
  - spm94 AC07: stubs an empty inbox, since every attendee now collects registration notices.
  - spm120 AC05: checks the `safety.rejected` notice by type and content.
  - spm55: allows for the slow dashboard (see Performance).

## Verification (1 Nov 2026, working tree on top of `c720d40`)

| Check | Result |
|---|---|
| Unit, all six services | 1,398 tests pass, 100% statement coverage in every service (up from 1,309) |
| Integration (`npm run test:integration`) | Pass |
| Live checks against the running services | Pass: registration on an app-confirmed event (notices, race), drafts hidden, missing fields listed, handoff for Venue Staff and Tech Support, queue speed, Lead and Safety catalogue access, the SPM-85 impact endpoint, the reminder run (due-soon alerts, expired holds) |
| e2e, the 23 specs touched or related | 175 pass, 23 fail on the first run. 9 of the 23 were fixed and pass on re-run (spm11 AC07 and AC08, spm55 AC01, AC03 and AC04, spm87 AC08, spm94 AC07, spm120 AC05, spm04 EXTRA05; spm55 then passed 7 of 7). The other 14 all read seeded e1, e2, e4 or vb-soon after earlier runs had changed them (spm11 AC01–AC04 and AC06, spm04 AC04 and EXTRA03, spm89 AC03 and AC06, spm105 AC03, spm108 AC02 and AC03, spm127 AC01, spm15 AC06). See Seed drift |

## Conflicts between stories (resolve in Jira)

- **SPM-14 AC4 and SPM-82 AC4 versus SPM-106 AC1.** "Offers the change request route" for a submitted event,
  against change requests opening only from Under Review. Resolved in the UI by showing the route disabled until
  a coordinator is reviewing the request. Reword AC4 to match, or add Submitted to SPM-106 AC1.
- **SPM-66 AC1 and AC7, and SPM-45 AC3** ("coordinators assign") are superseded by SPM-117 (only the Lead assigns).
  The code follows SPM-117.
- **SPM-93 AC5 versus SPM-11 AC3 and SPM-12 AC6.** "The actor is never notified" against "the attendee is
  notified of their registration or withdrawal".
- **SPM-127 versus the old spm11 spec.** Attendees may not open staff event pages, so registration lives on the
  public page `/app/browse/:id`.

## Test-suite caveats

- `npm run test:acceptance` (CI) still excludes about 55 story specs with `--grep-invert`. Run `npm run test:e2e`
  to see everything, after resetting the database (see Seed drift above).
- The SPM-87, SPM-77, SPM-78 and SPM-86 screens added here have no browser specs of their own yet.
  spm87's UI tests exercise the reschedule dialog's test ids; the equipment actions are tested only through the API.
