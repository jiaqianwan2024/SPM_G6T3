# ConnectSphere API

Interactive OpenAPI (Swagger) docs for each FastAPI microservice. The spec is generated from routers and Pydantic models — do not hand-write a separate `swagger.yaml`.

Start the backends (`python scripts/dev-backend.py`), then open `/docs` on the service you need. `/redoc` is the same spec in a read-only layout. `/openapi.json` is the machine-readable file.

| Service | Port | Swagger UI | ReDoc |
|---|---|---|---|
| user-service | 8001 | http://localhost:8001/docs | http://localhost:8001/redoc |
| event-service | 8002 | http://localhost:8002/docs | http://localhost:8002/redoc |
| venue-service | 8003 | http://localhost:8003/docs | http://localhost:8003/redoc |
| equipment-service | 8004 | http://localhost:8004/docs | http://localhost:8004/redoc |
| registration-service | 8005 | http://localhost:8005/docs | http://localhost:8005/redoc |
| notification-service | 8006 | http://localhost:8006/docs | http://localhost:8006/redoc |

`GET /health` on every service is public. Routes that one service calls on another with no user signed in take the `X-Service-Key` header (the `INTERNAL_SERVICE_KEY` setting) instead of a token: the `/internal/...` routes, `POST /notifications/publish`, and `POST /events/reminders/run` (which also accepts a coordinator or the Coordinator Lead). Every other route expects a Firebase ID token.

## Auth in Swagger

1. Sign in through the Vue app with a [demo account](architecture.md#demo-logins).
2. Copy the ID token (browser console: the Network tab on any API call → `Authorization: Bearer …`, token only).
3. In `/docs`, click **Authorize**, paste the token (not the word `Bearer`), and **Try it out**.

Role gates (enforced by forwarding the token to `GET /users/me`):

| Action | Role |
|---|---|
| `POST /events` | `organiser` |
| `GET /events`, `/events/all`, `/events/confirmed`, `/events/{id}`, `/events/{id}/activity-log` | Any role except `attendee` (SPM-127: 403 "Attendees can open only confirmed event pages and their own registrations.") |
| `GET /events/mine` | `organiser`: their client organisation's events at any stage, colleagues' included, with only their own drafts and nothing discarded (SPM-47) |
| `GET /events/{id}`, `/activity-log`, `/readiness`, `/readiness-items/{item}`; `GET /equipment/reservations/summary` | An `organiser` only for their own organisation's events, else 403 "You can only open your own organisation's events." (SPM-47); staff for any event. Event lists are limited to the organiser's organisation |
| `GET /events/{id}/attendee-card` | Staff and organisers for any event; an `attendee` only for a `confirmed` event or one they hold a registration for (SPM-127), else 403. Public fields only, including `registrationEnabled` and the registration period |
| `GET /registrations/mine/event-ids` | The signed-in user: ids of the events they hold a registration for (SPM-127). It never calls event-service, so the two services cannot loop |
| `GET /users`; `GET /equipment`, `/equipment/{id}`, `/equipment/{id}/activity-log`, `/equipment/reservations/summary` | Any role except `attendee` (SPM-127, 403) |
| `GET /events/upcoming/technical` | `techsupport` |
| `POST /events/{id}/assign-coordinator` | `coordinatorlead` only (SPM-117, SPM-118); an Event Coordinator gets 403. The assignee must be a `coordinator` (422 otherwise) |
| `GET /events/coordinators` | `coordinatorlead` |
| `GET /events/assignments` | `coordinatorlead` only (SPM-119); an Event Coordinator gets 403 |
| `GET /events/queue` | `coordinatorlead` sees every request; a `coordinator` sees only the requests assigned to them |
| `GET /events/assigned` | `coordinator` only: the caller's own assigned events at any stage except draft and discarded, soonest first. Filtered in the database, so `registeredCount` is only fetched for those rows. Every other role gets 403 |
| `POST /events/{id}/reject` | `coordinator` assigned to the event (SPM-70) |
| `POST /events/{id}/cancel` | `organiser` of the event's organisation, or the `coordinator` assigned to it (SPM-88). Any live status (409 for draft, discarded, rejected, completed, or already cancelled); a `reason` is required (422). Venue bookings and equipment reservations are released first, side by side; if either fails, what was released is given back, the event is unchanged, and 503 says so. Then the event is `cancelled` (terminal), with `cancellationReason`, `cancelledBy`, `cancelledAt`; the change is in the activity log and a pending change request becomes `closed`. Attendees, the coordinator, the organiser, the approving Venue Staff, and the technical support members who handled its lines get `event.cancelled` just after the reply |
| `POST`, `PATCH`, `DELETE /events/{id}/readiness-items…` | `coordinator` assigned to the event |
| `GET /events/{id}/coordinator` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport` |
| `POST /events/{id}/approve` | `coordinator` assigned to the event (SPM-69); only while it is `under review` or `changes requested` |
| `GET /events/{id}/decision` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport` |
| `GET /events/{id}/clarifications` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport` (SPM-68) |
| `POST /events/{id}/clarifications`, `POST /events/{id}/clarifications/{cid}/resolve` | `coordinator` assigned to the event (SPM-68) |
| `POST /events/{id}/clarifications/{cid}/reply` | `organiser` of that event's organisation, or the assigned `coordinator` |
| `POST /events/{id}/safety-handoff/venue` | `venue` (SPM-120, change 6); only from `planning` |
| `POST /events/{id}/safety-handoff/technical` | `techsupport` (SPM-120, change 6); only from `planning` |
| `GET /events/{id}/safety-handoff` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport`, `safety` |
| `POST /events/{id}/safety-reviews` | `coordinator` assigned to the event (SPM-120); only from `planning` |
| `GET /events/safety-reviews` | `safety` |
| `GET /events/{id}/safety-reviews` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport`, `safety` |
| `POST /events/{id}/safety-reviews/{rid}/claim` | `safety`; 409 once another officer has claimed the event |
| `POST /events/{id}/safety-reviews/{rid}/approve`, `/reject`, or `/request-changes` | the `safety` officer who claimed the event; another officer and every other role get 403, an unclaimed review is 409 |
| `GET /events/{id}/confirmation`, `POST /events/{id}/confirm` | `coordinator` assigned to the event (SPM-72); confirming only from `safety approved` |
| `POST /events/{id}/reschedule/preview`, `POST /events/{id}/reschedule` | `coordinator` assigned to the event (SPM-87); approved, planning, or confirmed |
| `POST` or `DELETE /events/{id}/equipment-lines/{equipmentId}/not-required` | `coordinator` assigned to the event (SPM-72); only in `planning` |
| `PATCH /events/{id}/registration-settings` | `coordinator` assigned to the event (SPM-90); from `planning` until `confirmed` |
| `GET /events/{id}/change-requests` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport` (SPM-106) |
| `POST /events/{id}/change-requests` | `organiser` of that event's organisation (SPM-106) |
| `POST /events/{id}/change-requests/{crid}/withdraw` | the `organiser` who raised it |
| `POST /events/{id}/change-requests/{crid}/accept` or `/decline`; `GET /events/{id}/change-requests/{crid}/impact` | `coordinator` assigned to the event (SPM-106, SPM-85) |
| `POST /notifications/records` with another user's `userId` | `coordinator`, `venue`, `techsupport` (anyone may name themselves) |
| `POST /notifications/clear-all`, `POST /notifications/{id}/clear`; `GET /notifications?bell=true` | signed-in caller, their own notifications only; another user's id is 404 (SPM-94). Clearing hides from the bell and marks read; nothing is deleted |
| `POST /notifications/publish` | another service, sending the `X-Service-Key` header (SPM-93). No user token is used; with no `INTERNAL_SERVICE_KEY` configured every call gets 403 |
| `PATCH /events/{id}` | `coordinator` assigned to the event (SPM-71); not while it is completed, cancelled, rejected, a draft, or discarded |
| `GET /events/{id}/internal-notes` | `coordinator` |
| `GET /events/significant-fields` | signed-in caller |
| `GET /venues`, `GET /venues/{id}`, `GET /venues/{id}/activity-log` | `coordinator`, `venue`, `techsupport` |
| `POST /venues`, `PATCH /venues/{id}`, `POST /venues/{id}/retire` | `venue` |
| `POST /venues/{id}/unavailability` | `venue` (SPM-115). Saves a block and does not read or change the event. If the block overlaps an approved booking, `acknowledgeConflicts` must be true; that booking stays approved |
| `GET /venues/{id}/calendar` | `coordinator`, `coordinatorlead`, `venue`, `techsupport`, `safety` (SPM-108). Every confirmed booking, pending request, active or expired hold, and unavailability period overlapping the optional `from`/`to` range, each with a `kind`. A booking's `startsAt`/`endsAt` is its occupied window; `eventStartsAt`/`eventEndsAt` are the advertised times. Rejected, withdrawn, and cancelled requests are left out. Includes the venue's opening hours (SGT). An empty range returns `entries: []` |
| `GET /venues/search` | `coordinator`, `venue` (SPM-61); with `eventId`, each result also carries that event's suitability `verdict` (SPM-62 AC9) |
| `POST /venues/suitability` | `coordinator`, `venue` |
| `POST /venues/bookings` | `coordinator` assigned to the event (SPM-63) |
| `GET /venues/bookings`, `GET /venues/bookings/{id}` | `coordinator`, `venue` |
| `GET /venues/dashboard` | `venue` only, as Booking Requests is (SPM-57). `pending` (oldest first), `reverification` (approved bookings flagged after an event change) and `upcoming` (approved bookings under way or starting within `upcomingDays`, 7), both soonest first; events that have ended are left out |
| `GET /venues/bookings/clashes` | `venue` (SPM-122); read only, lists confirmed bookings whose occupied windows overlap under the venue's current setup and turnaround |
| `POST /venues/bookings/{id}/withdraw` | `coordinator` assigned to the event (SPM-46), so after a reassignment the new coordinator |
| `POST /venues/bookings/{id}/cancel` | `coordinator` assigned to the event, or `venue` (SPM-114) |
| `POST /venues/bookings/{id}/replacement` | `coordinator` assigned to the event (SPM-115). The booking must be `approved` and overlap an unavailability block. The new venue is checked on its own, using the booking's existing time and the event's current details. On success the original booking becomes `cancelled` and stays readable; the event is not changed |
| `POST /venues/bookings/release` | `coordinator` assigned to the event, or an `organiser` from the event's own client organisation (SPM-114). Each released booking includes `previousStatus` (SPM-88) |
| `POST /venues/bookings/restore` | Same people as the release (SPM-88 AC9). Gives each named booking of the event that is still `cancelled` its previous status and any hold the release ended; 409 if its venue was approved for someone else meanwhile |
| `POST /equipment/reservations/release-for-event` | `coordinator`, `techsupport`, or the event's own `organiser` (SPM-88). Each released reservation includes `previousStatus` and `handledBy` |
| `POST /equipment/reservations/restore-for-event` | Same people as the release (SPM-88 AC9). Each named reservation of the event that is still `released` holds its stock again |
| `POST /venues/bookings/{id}/approve` or `/reject` | `venue`; only a `pending` request (409 otherwise, so an approved booking stays locked). Approval is refused (409), leaving the request pending, when a confirmed booking, unavailability, or another request's active tentative hold overlaps the occupied window (SPM-64, SPM-116); an expired hold does not count. A successful approval records `reviewedBy`, `reviewedByName` and `reviewedAt` (SPM-8). Rejecting (SPM-10) needs a `reason` (422 when blank) and may name `suggestedVenueId`, an active venue other than the one rejected (422 otherwise). It ends any tentative hold, so the request reserves nothing, and records `reviewedBy`, `reviewedByName`, `reviewedAt`, `decisionReason`, `suggestedVenueId` and `suggestedVenueName`. A rejected request can no longer be approved, rejected, withdrawn, held, or cancelled (409) |
| `POST /venues/bookings/{id}/hold` and `/hold/release` | `venue` (SPM-116); a hold needs a pending request and an `expiresAt` in the future and no later than the event's start, and is refused (409) when the venue is already taken for that window; the event's coordinator is told in the app until when |
| `POST /venues/bookings/reverification` | `coordinator`, `safety` (event-service calls it on a confirmed significant edit, or when a Safety Officer requests changes) |
| `POST /venues/bookings/{id}/recheck` | `coordinator`, `venue` (SPM-86). Reports the new window and does not move the booking |
| `POST /venues/bookings/reschedule/preview`, `POST /venues/bookings/reschedule` | `coordinator` assigned to the event (SPM-87) |
| `POST /venues/bookings/{id}/reconfirm` | `venue` (SPM-86). Moves an approved flagged booking onto the event's current times, or releases that booking |
| `POST /equipment/requests` | `coordinator` assigned to the event (SPM-46). Every technical support member is told a request is waiting (`equipment.requested`) |
| `PATCH /equipment/requests/{id}/details` | `coordinator` assigned to the event (SPM-46), and only while the request is still pending. A change to the quantity or requirements tells technical support (`equipment.request_changed`); resubmitting a request and accepting a shortfall do too. Both notices open the event's equipment page and are best effort, so a failed notice never undoes the change |
| `POST /equipment/requests/{id}/review`, `/reserve`, or `/unavailable` | `techsupport` |
| `PATCH /equipment/requests/{id}` | refused |
| `POST /equipment/availability` with `eventId` | signed-in caller |
| `POST /equipment/reservations/{id}/release` | `techsupport` |
| `GET /equipment/reservations?eventId=` | `coordinator`, `techsupport` |
| `POST /equipment/reservations/reverification` | `coordinator`, `safety` (event-service calls it on a confirmed significant edit, or when a Safety Officer requests changes) |
| `POST /equipment/reservations/reschedule/preview`, `POST /equipment/reservations/reschedule` | `coordinator` assigned to the event (SPM-87) |
| `GET /equipment/queue` | `techsupport` (SPM-86). Held reservations still waiting for re-verification |
| `GET /equipment/dashboard` | `techsupport` (SPM-58). Technical support's home screen in one reply: `pending` requests awaiting review, reservations flagged for `reverification`, unresolved `shortfalls` (requests `partial` or `unavailable`; an accepted shortfall is `resolved` and left out), and `upcoming` events with equipment held for them. Each item carries its event's name and dates. Only events that have not ended and are not cancelled, completed, rejected, or a draft are included; every list is soonest first. The lists are the whole team's |
| `POST /equipment/reservations/{id}/reconfirm` | `techsupport` (SPM-86). Clears the flag and does not raise the reserved quantity |
| `POST /events/{id}/reverification/settle` | `venue`, `techsupport`, `coordinator` (SPM-86). Returns a `reconsidering` event to `confirmed` only when every flag is clear |
| `POST /events/{id}/attendee-notice` | `venue`, `coordinator` (SPM-86). Tells registered attendees the date, time, or venue changed |

## Assigning a coordinator (SPM-117, SPM-118, SPM-119)

A new request stays unassigned in the review queue until the Event Coordinator Lead (role `coordinatorlead`; demo account `lead@connectsphere.com` / `lead123`) assigns it to an Event Coordinator. The Lead can reassign it later. Coordinators manage only the events assigned to them:

- their review queue shows only their own requests;
- assigning, reassigning, and listing candidates return 403 for them.

This replaces SPM-66, under which any coordinator could assign.

`GET /events/coordinators` lists every Event Coordinator as `{userId, name, email, activeEventCount}`. The count covers their assigned events that are not completed, cancelled, rejected, drafts, or discarded, and is for information only: there is no workload limit.

`POST /events/{id}/assign-coordinator` with `{"coordinatorId": "u6"}` assigns or reassigns the event.

- **Status:** a `submitted` event moves to `under review`; other statuses are unchanged.
- **Reassigning (SPM-118):** the event must move to a different coordinator. Choosing the one it already has is 409 and saves nothing. Edit permission moves at once: every service reads the event's coordinator on each request.
- **Activity log:** the assignment appears in `GET /events/{id}/activity-log` as a `kind: "assignment"` entry: `changedBy` (the Lead) assigned `newValue`, replacing `oldValue`, at `createdAt`.
- **Who's told:** by email and in-app, the new coordinator (`event.assigned`), the organiser (`event.coordinator`), and on a reassignment the coordinator it was taken from (`event.reassigned`). Assigning the coordinator it already has tells no one. This step is best effort, so a failed notice does not undo the assignment.
- **Errors:** 409 for completed, cancelled, rejected, draft, or discarded events; 422 when the assignee is not a coordinator; 503 when user-service cannot be reached (nothing is saved then).

Only the assigned coordinator can approve (SPM-69) or reject (SPM-70) a request; reject accepts `submitted` or `under review`.

`GET /events/assignments` (SPM-119, Lead only) lists every Event Coordinator by name as `{userId, name, email, events}`. `events` holds their active events, soonest first, as `{eventId, eventName, status, proposedStartAt, proposedEndAt, organisationName}`; active means not completed, cancelled, rejected, draft, or discarded. A coordinator with no active events is still listed. An event assigned to someone no longer listed as a coordinator appears under that user's id. The Lead's **Assignments** tab shows this list, and each event opens its page, where the Lead can reassign it.

`GET /events/{id}/coordinator` returns `{coordinatorId, name, email}`, all null until someone is assigned. It is kept off `GET /events/{id}` so attendees never see it.

## Approving a request (SPM-69)

`POST /events/{id}/approve` with `{"note": "Ready for planning"}` (the note is optional, up to 2000 characters, and shown to the organiser) moves an `under review` request to `planning`. Only the event's assigned coordinator can approve (403 for any other coordinator). A request with no coordinator, such as a `submitted` one, cannot be approved (409), and neither can one that is past review (409).

The decision is stored in `event_reviews` (`action: "approve"`, reviewer, note, time). The status change appears in `GET /events/{id}/activity-log` without the note, because attendees can read the log. The response is the event plus `decision`, `decisionNote`, `decidedBy`, and `decidedAt`. The organiser is emailed through notification-service. This is best effort, so a failed email does not undo the approval.

An event with an open clarification (`hasOpenClarifications: true`, see SPM-68 below) returns 409 and saves nothing until the coordinator confirms:

```json
{
  "detail": {
    "message": "This request still has open clarifications with the organiser. Confirm to approve it anyway.",
    "requiresConfirmation": true,
    "openClarifications": true
  }
}
```

Resend with `"confirmOpenClarifications": true` to approve.

Approval does not call venue-service or equipment-service, so no venue is booked and no equipment is reserved. Those arrangements stay outstanding.

`GET /events/{id}/decision` returns `{decision, decisionNote, decidedBy, decidedAt}`, all null until a decision is made. Like the coordinator's contact details, it is kept off `GET /events/{id}`, so attendees never see the note.

## Clarifications (SPM-68)

`POST /events/{id}/clarifications` with `{"message": "Please confirm expected attendance.", "field": "expectedAttendance"}` opens a clarification. `field` is optional and must be a field of an event request (422 otherwise), and the message cannot be blank. Only the assigned coordinator can raise one (403 for any other coordinator), and only while the request is `under review` or `changes requested`. A draft, an event with no coordinator, and an event past review are 409. The request moves to `changes requested` and the organiser is emailed (best effort). Several clarifications can be open at once, and each is open or resolved on its own.

`POST /events/{id}/clarifications/{cid}/reply` with `{"message": "Attendance stays at 80."}` adds to the thread (201). The organiser, a colleague in their organisation, or the assigned coordinator can reply; the other side is emailed. An organiser's reply also publishes `clarification.replied` to the assigned coordinator's inbox (SPM-6): the title names the event, the body includes the event id and the reply, and the row links to `/app/events/{id}`. No inbox row is written before that reply, and the clarification stays `open`. If the event is no longer `under review` or `changes requested`, the email and the inbox both say it is no longer awaiting review and name the status it is now. A resolved clarification takes no more replies (409).

`POST /events/{id}/clarifications/{cid}/resolve` (assigned coordinator only) marks it resolved; resolving one twice is 409. When no clarification is left open, a `changes requested` request returns to `under review`. An event that has moved on keeps its status.

`GET /events/{id}/clarifications` lists every thread, oldest first, at any stage, including after the event is confirmed, completed, or cancelled. Organisers see them for their own organisation's events and staff for any event; attendees get 403. Each thread is returned as follows; `entries` holds the question, then every reply, oldest first:

```json
{
  "clarificationId": "rv-clarify-e3",
  "eventId": "e3",
  "message": "Please confirm expected attendance.",
  "field": "expectedAttendance",
  "status": "open",
  "raisedBy": "u2",
  "createdAt": "2026-10-01T09:00:00",
  "resolvedBy": null,
  "resolvedAt": null,
  "entries": [
    {"entryId": "rv-clarify-e3", "authorId": "u2", "authorName": "Ben Lee", "authorRole": "coordinator", "message": "Please confirm expected attendance.", "createdAt": "2026-10-01T09:00:00"},
    {"entryId": "…", "authorId": "u1", "authorName": "Alice Tan", "authorRole": "organiser", "message": "Attendance stays at 80.", "createdAt": "2026-10-01T11:30:00"}
  ]
}
```

`authorName` is null when user-service cannot be reached. Questions and replies are kept off `GET /events/{id}` and the activity log, which only record the status changes. Every event read includes `hasOpenClarifications`.

## Registration settings (SPM-90)

`PATCH /events/{id}/registration-settings` takes only the fields that change: `registrationEnabled`, `registrationOpensAt`, `registrationClosesAt`, and `capacity`. Only the assigned coordinator can use it (403 for any other coordinator, 409 with no coordinator). It works while the event is in planning, safety review, safety approved, preparing, prepared, confirmed, or reconsidering; any other status is 409. Times with a UTC offset are stored as UTC, to the second. The period can be cleared with `null`; `registrationEnabled` and `capacity` cannot.

- Registration must close after it opens and no later than the event's start (422). This is checked whenever the request includes either period field.
- A `capacity` below the number currently registered is 409 and cannot be confirmed: `{"detail": {"message": "2 people are already registered, so the capacity cannot go below 2.", "registeredCount": 2}}`.
- The coordinator must confirm two situations: a `capacity` above what a confirmed venue booking holds in the event's layout, and turning registration off while attendees are registered. Until then the endpoint returns 409 and saves nothing. The response names both figures:

```json
{
  "detail": {
    "message": "A capacity of 500 is more than Marina Hall A holds in the Theatre layout (300). 2 attendees are already registered. Turning registration off will notify them.",
    "requiresConfirmation": true,
    "warnings": [
      {"kind": "venueCapacity", "capacity": 500, "venueCapacity": 300, "venueName": "Marina Hall A", "layout": "Theatre", "message": "…"},
      {"kind": "registrationOff", "registeredCount": 2, "message": "…"}
    ]
  }
}
```

Resend with `"confirmOverVenueCapacity": true` and/or `"confirmRegistrationOff": true` to save. A capacity sent unchanged is still checked against the booking and the registrations, because those can change on their own.

Each changed setting is written to `GET /events/{id}/activity-log` as a `kind: "edit"` entry. The organiser is emailed and gets an in-app notification (`event.registration_settings`) naming what changed. When registration is turned off, each registered attendee is emailed and, if they have an account, notified in-app (`registration.closed`). Their registrations stay in place, and `notifiedAttendees` in the response counts them. If registration-service or venue-service cannot be reached, the endpoint returns 503 and saves nothing. The settings are on every event read, and organisers see them on their event page.

## Safety review (SPM-120)

A Safety Officer (role `safety`; demo account `safety@connectsphere.com` / `safety123`) reviews an event once its venue and technical arrangements are confirmed. While a review is pending, the event's status is `safety review`.

Week 7 change 6: the staff who confirmed each arrangement send it to the Safety Officer. The review opens once every part the event needs is in:

- `POST /events/{id}/safety-handoff/venue` with `{"crowdMovement": "…"}`: Venue Staff send the venue arrangements. Refused (409, `missing: ["venue"]`) until every requested venue is `approved` for the event's own date and time.
- `POST /events/{id}/safety-handoff/technical` with `{"equipmentPlacement": "…"}`: technical support send the technical arrangements. Refused (409, `missing: ["equipment"]`) until every equipment line is reserved or recorded as not required, and 409 when the event has no equipment at all.
- Both return the hand-off: `venue` and `technical` (`sentBy`, `sentAt`, `note`, or null), `technicalNeeded` (false when the event has no equipment, so the venue part alone is enough), and `review`, which is set when this part opened the review.
- **Opening:** the last part needed opens the review, after checking all the arrangements again. If the other part's arrangements changed since it was sent, that part is cleared and must be sent again. The coordinator is told the review has started.
- **Resending:** sending a part again replaces its note. A significant change to the event clears both parts.
- `GET /events/{id}/safety-handoff` shows what has been sent this round.

`POST /events/{id}/safety-reviews` with `{"crowdMovement": "…", "equipmentPlacement": "…"}`: the assigned coordinator can also submit a `planning` event with both notes at once (201), for example after revising rejected arrangements (AC9). This replaces any part already sent.

- **When it's allowed:** once the venue and equipment pass the same check as confirming (see SPM-72 below). Every requested venue is `approved` for the event's own date and time. Every equipment request is reserved, complete, or accepted short. Every equipment line on the event is held or recorded as not required. An event needing no equipment has nothing technical to wait for.
- **When it's refused:** until then it returns 409 with `{"message": …, "missing": ["venue", "equipment"], "gaps": [{"kind": "venue", "message": …}]}`. If venue-service or equipment-service can't be reached, it returns 503 and nothing is submitted.
- **What's saved:** a copy of what the officer reviews, as `package`:
  - expected attendance;
  - each booked venue with its capacity in the event's layout (its largest layout when it doesn't offer that one), layouts, accessibility features, emergency access, known restrictions and opening hours;
  - the event's accessibility requirements;
  - the equipment lines;
  - the equipment placement (required when the event has any equipment);
  - crowd movement.
- **Flags:** a booking or reservation with `needsReverification` does not count. The submission is 409, naming the re-verification, and nothing is submitted until Venue Staff or technical support re-confirm it (SPM-86).
- **Who's told:** every Safety Officer is notified until one claims the event. After that, every later round goes to that officer alone.

`GET /events/safety-reviews?status=pending` is the officers' queue, longest-waiting first. `GET /events/{id}/safety-reviews` lists an event's reviews, newest first, for the organiser's organisation and staff.

**One officer per event.** `POST …/{rid}/claim` makes the caller the event's Safety Officer (`safetyOfficerId` on every review of the event). Claiming the pending review of an event you already hold returns it unchanged. If another officer holds it, the response is 409 naming them. A review that is not pending is 409. Claims are atomic, so two officers claiming at once cannot both win. The coordinator gets an email and an in-app notice (`event.safety_review`) naming the officer. The officer keeps the event across rejections, change requests, and resubmissions; there is no release yet.

Decisions apply to the pending review, by the Safety Officer who claimed the event only. An unclaimed review is 409 (`Claim this safety review before deciding on it`), another officer is 403, and every other role gets 403:

- `POST …/{rid}/approve` with an optional `note`: records `decidedBy` and `decidedAt`, and the event moves to `safety approved`. The coordinator then confirms it (SPM-72).
- `POST …/{rid}/reject` with a required `reason`: the event returns to `planning`. It doesn't proceed to preparation and isn't cancelled; the coordinator can revise the arrangements and submit again.
- `POST …/{rid}/request-changes` with a required `requiredChanges` and optional `affected` (`venue`, `technical`): the event returns to `planning`. The named arrangements are flagged for re-checking by venue staff or technical support. If a flag can't be set, it returns 503 and nothing is saved.

After every decision, the assigned coordinator and the organiser get an email and an in-app notice (`event.safety_review`).

A significant edit or accepted change request while the review is pending returns the usual 409 (`statusChange` from `safety review` to `planning`) until confirmed. Then the review becomes `superseded` and the event goes back to `planning`. The same applies after approval and before confirmation (`statusChange` from `safety approved` to `planning`). The approval stays in the history, and the event needs a new safety review.

Venues carry `emergencyAccess` and `restrictions` text, kept by venue staff in the catalogue.

## Confirm an event (SPM-72)

The assigned coordinator confirms an event after the Safety Officer approves it. Venue-service and equipment-service are checked again at that moment, so a booking cancelled or a reservation released since the safety review blocks confirmation.

`GET /events/{id}/confirmation` says whether the event can be confirmed and, if not, names each missing arrangement:

```json
{
  "eventId": "e3",
  "ready": false,
  "missing": [
    {"kind": "venue", "message": "The booking at Marina Hall A (01 Dec 2026 09:00 to 01 Dec 2026 12:00) is not for the event's date and time. Cancel it and request the venue for the event's time."},
    {"kind": "equipment", "equipmentId": "eq1", "message": "1 × Projector is neither reserved nor recorded as not required."},
    {"kind": "safety", "message": "It has not been sent for a safety review yet. Venue Staff and technical support send their arrangements once they are confirmed."}
  ]
}
```

Confirming needs all of these:

- **Venue:** at least one booking, every live booking `approved` by venue staff, and each one covering the event's current start and end. A booking left at an earlier time after the event moved doesn't count. A booking flagged for re-verification does not count until Venue Staff re-confirm it (SPM-86). Cancel one that no longer fits (`POST /venues/bookings/{id}/cancel`) and request the venue for the new time.
- **Equipment:** every request is reserved, complete, or a shortfall the coordinator accepted. Every equipment line on the event is held by reservations or recorded as not required. A gap that can be recorded as not required carries its `equipmentId`.
- **Safety:** the event is `safety approved`. A pending, rejected, or changes-requested review, or none at all, is named with its note.

`POST /events/{id}/confirm` (no body) moves `safety approved` to `confirmed`. It stores `confirmedBy` and `confirmedAt` on the event, and the response also carries them as `decidedBy` and `decidedAt`.

- Anything missing returns 409 with `{"message": …, "missing": ["venue", "equipment", "safety"], "gaps": […]}` and saves nothing.
- An event that is already confirmed is 409.
- If venue-service or equipment-service can't be reached, it returns 503.

Once confirmed, each of these people gets an email and an in-app notice (`event.confirmed`). Each person is told once:

- the organiser, with the venue, date and time, layout, equipment, and when registration opens;
- the venue staff who approved the bookings;
- the technical support who reserved the equipment.

A confirmed event with registration enabled appears in `GET /events/open-for-registration` once its registration period opens.

`POST /events/{id}/equipment-lines/{equipmentId}/not-required` with `{"reason": "The venue has a built-in projector."}` records that an equipment line is no longer needed.

- The reason is required (422 when blank). `DELETE` on the same path marks the line as needed again.
- Only the assigned coordinator can do this, and only while the event is in `planning` (409 otherwise). An unknown line is 404.
- The line gains `notRequired`, `notRequiredReason`, `notRequiredBy`, and `notRequiredAt`, and the change is written to the activity log.

## Preparation waits for safety approval (SPM-121)

Confirmed arrangements are not clearance to proceed:

- An approved venue booking and reserved equipment leave the event in `planning`. It is not `confirmed`, so attendees don't see it.
- The safety review starts only after the arrangement check above passes.
- The event becomes `confirmed`, and preparation can begin, only through `POST /events/{id}/confirm` after the Safety Officer approves.
- While the review is pending, rejected, or returned for changes, Confirm returns 409 with a `safety` gap.

`GET /events/mine` gives each of the organiser's events a `safetyReviewStatus`: the latest review's status (`pending`, `approved`, `rejected`, `changes_requested`, `superseded`), or `null` if the event was never submitted. The organiser's list uses it to show an event that is waiting on the review or was sent back with safety changes requested.

## Change requests (SPM-106)

`GET /events/changeable-fields` lists what an organiser can ask to change: `eventName`, `description`, `purpose`, `category`, `proposedStartAt`, `proposedEndAt`, `expectedAttendance`, `layoutPreference`, `accessibilityNeeds`, `equipmentRequirements`, and `equipmentLines` (SPM-85: `[{"equipmentId": "eq1", "quantity": 5}]`, a whole number of at least 1 each; only a change request can alter them, not `PATCH /events/{id}`).

`POST /events/{id}/change-requests` with `{"reason": "Client wants a dinner", "proposedChanges": {"layoutPreference": "Banquet"}}` raises a request (201). Who can raise one:

- The organiser who filed the event, or a colleague in their organisation, while it is under review (including `changes requested`), approved, in planning (including safety review, safety approved, preparing, and prepared), or confirmed (including `reconsidering`).
- Not for a draft (edited directly), a `submitted` request (no coordinator yet), or a completed, cancelled, or rejected event. These return 409.
- Not while another request is pending (409: withdraw it first).

The reason is required (422). Proposed values follow the same rules as `PATCH /events/{id}`, and other fields are 422. Only fields that actually differ are kept, and nothing to change is 422. The response includes `currentValues` alongside `proposedChanges`, plus `affectsVenue`, `affectsEquipment`, and `affectsRegistration`. The event itself is not touched, so its confirmed details still read as confirmed. The assigned coordinator is emailed.

`GET /events/{id}/change-requests` lists requests newest first. Organisers see them for their own organisation's events, staff for any event; attendees get 403.

- `POST …/{crid}/withdraw`: the organiser who raised a pending request takes it back (`withdrawn`). The coordinator is emailed.
- `GET …/{crid}/impact` (SPM-85): see [Reviewing a change request](#reviewing-a-change-request-spm-85).
- `POST …/{crid}/decline` with `{"reason": "Keep the original copy", "askNarrower": false}`: the assigned coordinator says no. The reason is required, and the event is unchanged. `askNarrower: true` (SPM-85 AC8) is how part of a request is agreed: it is still declined, nothing is applied, `narrowerRequested` is true, and the organiser is asked to raise a narrower request.
- `POST …/{crid}/accept` with `{"reason": "", "confirmSignificantChange": false}`: the assigned coordinator applies the proposed values under the `PATCH /events/{id}` rules. A significant change on an event with confirmed arrangements, or on a confirmed event, returns the same 409 until `confirmSignificantChange` is true. Then the arrangements are flagged (listed in `flaggedArrangements`) and a confirmed event becomes `reconsidering`. Accepting a new date or time tells every registered attendee after the save commits (SPM-86). Values that can no longer be applied are 422.

After accepting or declining, the organiser who raised the request is emailed and notified in-app (`event.change_request`), with the coordinator's reason, each arrangement an accepted change flagged for re-checking, and any request for a narrower change. Closing a request that is no longer pending is 409. `reviewedBy` and `reviewedAt` say who closed it and when. The decision is written to `GET /events/{id}/activity-log` as a `kind: "change_request"` entry: `decision` (`accepted` or `declined`), `changes` (each field with `oldValue`, its value when the request was raised, and `newValue`, the value asked for), `changedBy` (the coordinator), `note` (their reason), and `createdAt`. An accepted request's applied fields also appear as `edit` entries.

### Reviewing a change request (SPM-85)

`GET /events/{id}/change-requests/{crid}/impact` tells the assigned coordinator what accepting a pending request would affect. It changes nothing; a request that is no longer pending is 409, and an older one whose values cannot be applied is 422. Each part is read only when the request touches it:

- `venueBookings`: the event's confirmed venue bookings, when the start, end, attendance, layout, or accessibility needs change.
- `venueSuitability` (AC3): when the start, end, or layout changes, each booked venue's SPM-62 suitability check re-run at the proposed values, with its `verdict` and `reasons`. `null` when none of them changes; `[]` when nothing is booked.
- `capacity` (AC4): when the attendance or layout changes, each booked venue's `capacity` in the layout the event would have (`layout` is `null` when the venue does not offer it, so its largest capacity applies), the `expectedAttendance`, and `overCapacity`.
- `equipmentReservations`: reservations still holding stock, of every type when the event moves or its equipment notes change, otherwise only of the types whose quantity changes.
- `equipmentAvailability` (AC5): for each type whose quantity rises, `currentQuantity`, `proposedQuantity`, `extraQuantity`, `freeQuantity` (free during the event's period, the proposed one if it moves), `heldQuantity` (already reserved for this event in that period), `available`, and `shortfall`.
- `registrations`: the attendees currently registered, when the start, end, or attendance changes.
- `unchecked`: the parts (`venue`, `equipment`, `registrations`) whose service could not be reached. Their lists are empty, not clear.

The coordinator's page for this is `/app/events/{id}/change-requests/{crid}`, linked from the pending request on the event page.

## Editing an event (SPM-71)

`PATCH /events/{id}` takes only the fields that change. Name, description, purpose, category, internal notes, and organiser contact save without a warning. Start, end, expected attendance, layout, accessibility needs, and equipment requirements are significant; `GET /events/significant-fields` lists both groups.

A significant change on an event with a confirmed (`approved`) venue booking or an `active`/`reserved` equipment reservation, or on a `confirmed` event, returns 409 and saves nothing:

```json
{
  "detail": {
    "message": "Changing expected attendance affects arrangements that are already in place. …",
    "requiresConfirmation": true,
    "significantFields": ["expectedAttendance"],
    "arrangements": [
      {"kind": "venue", "id": "vb-soon", "summary": "Venue booking at Marina Hall A, …"},
      {"kind": "equipment", "id": "er-e1", "summary": "Equipment reservation: 2 x Projector"}
    ],
    "statusChange": {"from": "confirmed", "to": "reconsidering"}
  }
}
```

Resend with `"confirmSignificantChange": true` to save. The affected booking and reservations get `needsReverification: true` and a `reverificationNote` naming the change. Their status is unchanged, so the venue and stock stay held. A `confirmed` event moves to `reconsidering`, and the response lists `flaggedArrangements`. If venue-service or equipment-service cannot be reached, the edit is refused with 503 and nothing is saved. A date or time change tells every registered attendee after the save commits (SPM-86). The booking itself is not moved.

Every changed field is written to `GET /events/{id}/activity-log` as a `kind: "edit"` entry with `field`, `oldValue`, `newValue`, `changedBy`, and `createdAt`. Status changes stay `kind: "status"` entries. Internal notes are never on `GET /events/{id}`; coordinators read them from `GET /events/{id}/internal-notes`.

## Re-verifying arrangements (SPM-86)

A flagged arrangement is a gap. Safety submission and Confirm both refuse while any approved booking or held reservation still has `needsReverification`. There is no separate reverify status: the booking stays `approved` and the reservation stays `active` or `reserved`.

`POST /venues/bookings/{id}/recheck` takes optional `proposedStartAt` and `proposedEndAt`. When they are omitted, the event's current times are used. Coordinator or Venue Staff. The response includes `movedSilently: false`, `conflict`, `verdict`, `reasons`, and the booking's existing `startsAt` and `endsAt`. Only an `approved` booking can be re-checked. Nothing is saved.

`POST /venues/bookings/{id}/reconfirm` takes no body. Venue Staff only, and only when the booking is `approved` and flagged (otherwise 409). The check uses the event's current start and end, with the same suitability and occupied-window rules as a new booking.

- When the venue still suits the event and is free, the booking takes those times, the occupied window is recomputed from the venue's setup and turnaround, and the flag and note are cleared. The status stays `approved`.
- When it does not, that booking becomes `cancelled`, `reverificationNote` starts with `Released after re-verification`, and the response is 409 telling the coordinator to search again. The event's other bookings stay. Registered attendees are told the venue arrangement changed. A `reconsidering` event can request a venue again.

`GET /equipment/queue` lists `active` and `reserved` reservations that still need re-verification. Technical support only.

`POST /equipment/reservations/{id}/reconfirm` takes no body. Technical support only. The reserved quantity is never increased. If the event's line for that equipment wants more than the held quantity and the extra units are not free, the call is 409, the flag stays, and the quantity is unchanged. Otherwise the flag clears. A reservation that is not flagged is 409.

`POST /events/{id}/reverification/settle` takes no body. Venue Staff, technical support, or a coordinator. It returns `{eventId, status, restored}`. A `reconsidering` event becomes `confirmed` with `restored: true` only when the venue and equipment gaps are empty, including every re-verification flag. Any other status, including `safety approved` and `planning`, is left as it is and `restored` is false. Re-confirming a booking or reservation calls this.

`POST /events/{id}/attendee-notice` with `{"change": "schedule"}` or `{"change": "venue"}`. Venue Staff or a coordinator. Every registered attendee is told by email and in-app (`event.changed`). A date or time change on an edit or an accepted change request sends the schedule notice after the save commits. Releasing a booking on re-confirm sends the venue notice.

Flagging a booking notifies Venue Staff (`venue.reverification`). Flagging a reservation notifies technical support (`equipment.reverification`). A Safety Officer change request sets the same flag.

## Rescheduling (SPM-87)

The assigned coordinator moves an event to a new date, start and end. Only `approved`, `planning`, `confirmed`, and the stages the organiser reads as those (`safety review`, `safety approved`, `preparing`, `prepared`, `reconsidering`). Times are sent in UTC. The new start must be in the future and the end after it (422). Moving to the event's current time is 409. Another coordinator gets 403, and an event with no coordinator gets 409.

`POST /events/{id}/reschedule/preview` with `{proposedStartAt, proposedEndAt}` saves nothing (AC5). It returns:

- `venues`: each pending request and approved booking judged at the new occupied window, with the same suitability check as a new request and the event's own bookings left out. `free` is false when a confirmed booking, an active hold, or unavailability overlaps. `suitable` is false for any other failed point. Each has `verdict` and `reasons`.
- `venueFree` and `venueSuitable` cover every approved booking (null when nothing is booked). `unavailableVenues` names the ones that are not free or not suitable.
- `equipment`: each held reservation with `availableQuantity`, `canMeet` and `shortfall`. Other events' reservations are counted. The event's own are left out, and its reservations of the same equipment share what is free. `equipmentAvailable` covers them all.
- `registrationClosesAt` and `registrationCloseAdjusted` (AC8), and `messages`, one plain sentence per point.

`POST /events/{id}/reschedule` with `{proposedStartAt, proposedEndAt, reason, carryVenueBooking = true, confirmVenueUnavailable = false}`. `reason` is required.

- If an approved booking is not free or not suitable, the call is 409 with `requiresConfirmation` and `unavailableVenues`, and nothing changes (AC4). Abandoning means not sending it again. Resending with `confirmVenueUnavailable: true` releases those bookings and keeps the others.
- Bookings move first. A free and suitable approved booking is carried to the new time (`outcome: "carried"`), the occupied window is recomputed, and it is flagged with `needsReverification`. Venue Staff are told to re-confirm it through the usual re-confirm (AC3). Any other approved booking, or every one with `carryVenueBooking: false`, becomes `cancelled` (`released`). A pending request takes the new time (`moved`), and an active hold that would outlast the new start is released. If another event took a venue at the new time meanwhile, the call is 409 and nothing has moved. The old times are freed only here (AC5).
- Held equipment reservations then move. One whose quantity cannot be met is flagged, not dropped, and technical support are told (AC6). The event's open equipment requests take the new time too. If equipment-service cannot be reached, the reschedule still stands with `equipmentChecked: false`.
- A registration close after the new start becomes the new start (`registrationCloseAdjusted`, `previousRegistrationClosesAt`). If registration would only open at or after the new start, the call is 409 and the period must change first (AC8).
- Status follows the significant-change rule: `confirmed` becomes `reconsidering` until the venue is re-confirmed, a safety review or approval is withdrawn back to `planning`, and a safety hand-off must be sent again.
- `GET /events/{id}/activity-log` gets a `kind: "reschedule"` entry: `field: "schedule"`, the old and new period in `oldValue` and `newValue` (SGT), the reason in `note`, and `changedBy` and `createdAt` (AC9). The start and end also appear as `edit` entries.
- The organiser, Venue Staff and technical support get `event.rescheduled` with both periods and the reason. Registered attendees get the schedule notice (`event.changed`) (AC7).
- The approaching-event reminder (SPM-95) is checked straight away for the new date, so an event moved into the reminder window is reminded without waiting for the next run (AC10).

The response is the event plus `previousStartAt`, `previousEndAt`, `rescheduleReason`, `venues` (each with its `outcome`), `venueCarried`, `releasedVenues`, `equipment`, `equipmentChecked`, `registrationCloseAdjusted`, `notifiedAttendees`, and `messages`. 503 when the venue arrangements cannot be checked; nothing is saved then.

Event-service calls these on the coordinator's behalf; each is limited to the event's assigned coordinator:

- `POST /venues/bookings/reschedule/preview` and `POST /venues/bookings/reschedule`, with `{eventId, startsAt, endsAt}` plus `reason` and `carry` on apply.
- `POST /equipment/reservations/reschedule/preview` and `POST /equipment/reservations/reschedule`, with `{eventId, startsAt, endsAt}` plus `reason` on apply.

JSON is camelCase. Tables and conflict rules: [data-model.md](data-model.md). How to run the stack: [architecture.md](architecture.md). Acceptance tests: [testing/README.md](testing/README.md).
