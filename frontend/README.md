# ConnectSphere — Vue frontend

Every screen reads and writes through the microservices. API calls belong in
`src/api/` (`axiosClient.js` plus one file per microservice); a screen never
holds its own copy of the data. The services enforce every rule, so the screens
only mirror them to give earlier feedback.

## Run it

From the repo root:

```
npm run dev:frontend
```

Or from this folder:

```
npm install
npm run dev
```

Demo credentials are shown on the login screen (also in `src/auth/users.data.js`).
Each account logs into a different role's dashboard. Signing in goes through
Firebase; on a page refresh `main.js` restores the session from Firebase and
`GET /users/me`, so the user stays signed in.

## Folder structure

```
src/
  views/                   Route-level pages (Login, also the / entry point; Dashboard shell; /dev/ui catalogue)
  features/                One folder per dashboard tab or page
    dashboard/             Role home screens: organiser, attendee, technical support, default cards
    lead-dashboard/        Event Coordinator Lead home
    safety-reviews/        Safety Officer home and review queue
    my-events/  drafts/  create-event/              Organiser tabs
    assigned-events/  review-queue/  assignments/   Coordinator and Lead tabs
    event-detail/          /app/events/:id and its panels (decisions, edits, cancel, readiness, ...)
    event-calendar/
    venue-catalogue/       Venue list, add / edit form, activity log, tentative holds
    venue-calendar/        "Venue Calendar" tab (SPM-108)
    venue-request/         /app/events/:id/venues: search and suitability per venue
    booking-requests/      Venue Staff's "Booking Requests" tab
    unavailability/        Venue Staff's "Unavailability" tab
    equipment-catalogue/   Equipment list, detail, form, and an event's equipment check
    upcoming-events/       Technical Support's "Upcoming Events" tab
    browse-events/  my-registrations/               Attendee tabs
    notifications/         Bell, notifications page, and where a notice leads
  auth/
    users.data.js          Demo account reference shown on the login page
  store/
    session.js             Signed-in user (role, name, id)
    draftEditor.js         Unsaved-draft state for the New Request form
  api/                     Thin axios wrappers — not microservices
    axiosClient.js         One client per service; adds the Firebase token, signs out on 401
    userService.js  eventService.js  venueService.js
    equipmentService.js  registrationService.js  notificationService.js
  firebase.js              Firebase app and auth set-up
  config/
    roles.js               Which tabs exist per role
    eventStatus.js         Status labels and which statuses are locked
    eventFields.js         Event request fields and their labels
  utils/
    datetime.js            Singapore-time display and input helpers
    eventSchedule.js
  components/
    ui/                    Buttons, fields, tables, tabs, modal, ...
    layout/                App shell, navbar, page header, sections
    shared/                Logo, notification bell and menu, profile card, backdrops
  router/index.js          Routes + the auth guard on /app
```

`features/venue-catalogue/venues.data.js` and `features/browse-events/events.data.js`
are left over from before those screens read their services, and are not imported.

**Why this split**: `auth` and `store` aren't under `features/` because they
aren't tied to one tab — every tab depends on the session, and login isn't a
dashboard tab at all. `config/roles.js` is separate from any one feature
because it's the thing that decides *which* feature folders are even reachable
for a given role. If you add a real "Reports" tab later, its component and
data file belong in a new `features/reports/` folder, following the same
pattern — don't add it to `components/shared/`.

## What's implemented

The sections below describe the screens in more detail. Each story's acceptance
tests are listed in `docs/testing/README.md`.

**Login**
- Empty email/password blocks submission with inline errors
- Wrong credentials show one generic "Invalid email or password." message
- Correct credentials create a session and route to `/app`
- `/app` is guarded: no session redirects to `/login`. This client-side guard
  is a UX nicety only — every backend service independently verifies the
  Firebase ID token and returns 401 regardless of what the frontend does, so
  the API is protected even if this guard is bypassed entirely (e.g. calling
  the API directly with curl/Postman)
- Already-signed-in users hitting `/login` are redirected straight back to `/app`
- Logout signs out of Firebase, clears the session, and replaces the history
  entry; the guard re-runs on every navigation (including back/forward), so
  Back after logout bounces to `/login` rather than showing the dashboard
- Any API call that gets a 401 (e.g. an expired/revoked token) forces a
  client-side logout + redirect, so the app never sits silently broken
- Password input is masked, with a show/hide toggle

**Venue catalogue (SPM-60)**
- `features/venue-catalogue/` reads venue-service: list + detail panel showing
  code, location, address, description, capacity, facilities, accessibility,
  supported layouts, operating hours, and turnaround time
- Venue Staff can add, edit, and retire a venue; retiring a venue with a
  confirmed upcoming booking shows those bookings and asks to confirm first.
  Coordinators and Technical Support can only view
- Every change is shown in the venue's activity log, with times in Singapore time (SGT)
- Venue Staff see confirmed bookings that clash once setup and turnaround are
  included (SPM-122): a banner over the venue list names each venue with clashes,
  and the venue's details list each pair with both events, their times, and the
  overlap in Singapore time. The list refreshes after a venue is saved. It only reads; the
  bookings and their events are kept as they are
- Venue Staff can place a tentative hold on a venue's pending request until a
  date and time (SGT), or release it early (SPM-116), in the venue's "Tentative
  holds" section. The coordinator's Choose venues page shows "Held until ..."
  on that request, or "Hold expired" once the time has passed

**Singapore time (SGT)**
- ConnectSphere's venues are in Singapore, so every screen shows and takes times in
  Singapore time (UTC+8), whatever the viewer's computer is set to. The server keeps
  UTC. `src/utils/datetime.js` holds the shared helpers: `formatSgt`, `formatSgtDate`,
  `formatSgtTime` and `formatSgtRange` for display, `toSgtInput` and `fromSgtInput`
  for datetime-local inputs (sent as UTC without a zone marker), and `sgtDay`,
  `sgtDayStart` and `sgtDayEnd` for date filters. The venue calendar runs in the
  `Asia/Singapore` time zone

**Booking Requests (SPM-8)**
- `features/booking-requests/` is Venue Staff's "Booking Requests" tab. It lists
  pending requests, oldest first, filtered by venue if wanted. Each shows the event's
  times, the venue's occupied window (with setup and turnaround), the event's
  requirements, the coordinator's notes and accepted warnings, the submission time,
  and any tentative hold, all in Singapore time (SGT)
- Requests that compete for the same venue at overlapping times are marked with
  their place ("Competing request 1 of 3")
- "Approve" takes an optional note. A refusal (an overlapping confirmed booking,
  unavailability, or active hold) is shown on the request, which stays pending
- The Approved view shows who approved each booking and when
- "View full details" lists everything the request carries (SPM-10 AC1)
- "Reject" asks for a reason and, optionally, another venue to suggest; Confirm
  rejection stays disabled until a reason is typed. The Rejected view shows who
  rejected each request, when, why, and the suggestion (SPM-10). The coordinator's
  Choose venues page shows the reason and suggestion next to the rejected booking

**Venue suitability (SPM-62)**
- `features/venue-request/` opens from "Choose a venue" on an event
  (coordinators only). Picking a venue shows suitable, suitable with warnings,
  or not suitable, with a reason for each point
- "Request this venue" is disabled on any failure and allowed with warnings

**Venue search (SPM-61)**
- The same page has a search panel filled in from the event (dates, attendance,
  layout, and any listed facility or accessibility feature named in the event's
  requirements). Searching narrows the venue list; "Show all venues" restores it
- Each result shows its capacity in the layout and the spare places, and a
  "Contested" tag when another event's request for that time is waiting
- After a search, each venue also shows its suitability verdict (SPM-62 AC9),
  the same one the check gives when that venue is picked

**Venue booking requests (SPM-63)**
- On the same page, the assigned coordinator sends the request for an event
  approved for planning, with optional notes for Venue Staff. With warnings,
  they must first tick that they have read them
- While the event has a pending request, the page shows it with a
  "Withdraw request" button. The same venue cannot be requested again while
  that booking is pending or approved; another venue can be (SPM-114)
- Venue Staff review requests on Booking Requests (SPM-8). The venue calendar
  and the readiness view are other stories (SPM-108, SPM-5)

**Attendee registration**
- `features/browse-events/` lists the confirmed events open for registration,
  read from event-service. Opening one shows its public details and places left
- The Register button is disabled with the specific reason shown when a rule
  fails; submitting requires name + email; success shows a confirmation.
  registration-service checks the same rules again (confirmed event, open
  window, capacity, no duplicate) when the registration is sent
- `features/my-registrations/` lists the attendee's own registrations; opening
  one shows its details and lets them withdraw before the event starts

**Venue calendar (SPM-108)**
- `features/venue-calendar/` shows one venue's confirmed bookings, pending
  requests, active and expired holds, and unavailability, each in its own
  colour and label, by week or by month, including past dates
- A booking spans its occupied window (setup and turnaround hatched in the week
  view) and shows the event's name, client, and advertised time; clicking it
  opens the event, or the held request on Booking Requests for Venue Staff
- Time outside the venue's opening hours is shaded, and closed days say so

**Technical Support home (SPM-58)**
- `features/dashboard/TechDashboard.vue` lists requests awaiting review,
  reservations to re-verify, unresolved shortfalls, and upcoming events with
  equipment held. Each item opens the event's equipment page

**Venue Staff home (SPM-57)**
- `features/dashboard/VenueHome.vue` reads `GET /venues/dashboard` and lists booking
  requests awaiting a decision, confirmed bookings flagged for re-verification (with
  what changed), and confirmed bookings in the next 7 days (with the setup time), built
  from the `/dev/ui` pieces (StatGrid, SectionBlock, UiEmptyState). A request or a
  flagged booking opens it on Booking Requests; an upcoming booking opens the venue
  calendar on its day. It replaced the placeholder cards Venue Staff used to see

**Cancelling an event (SPM-88)**
- The organiser, or the assigned coordinator, cancels from the event page.
  The dialog states what will be released and who will be told, and needs a
  reason. A failed release leaves the event unchanged and shows why. A
  cancelled event shows its reason

## What's NOT here

- Some tabs still show "not built yet for this sprint": Reports and Venue
  Requests (coordinator), Reservations, My Assignments, and Maintenance Status
  (technical support), and Waiting List (attendee)
- The orb is an original swirling-marble design with a single orbit ring —
  deliberately not shaped like a two-tone capsule or any branded "capture ball"
