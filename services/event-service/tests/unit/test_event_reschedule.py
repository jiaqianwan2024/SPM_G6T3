from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.event import Event
from app.models.event_safety_review import EventSafetyReview
from app.models.event_status_history import EventStatusHistory
from app.schemas.event import RescheduleIn
from app.services.reminders import EventReminders
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import service_unavailable
from shared.testing.cases import ServiceTestCase
from tests.unit.support import EventCase, insert_event

DAY = timedelta(days=1)
START = (datetime.utcnow() + 30 * DAY).replace(hour=2, minute=0, second=0, microsecond=0)
END = START + timedelta(hours=3)
NEW_START = START + 7 * DAY
NEW_END = END + 7 * DAY
HEADERS = {"Authorization": "Bearer token"}


def venue(booking_id="vb-1", name="Marina Hall A", status="approved", free=True, suitable=True, **extra):
    return {
        "bookingId": booking_id,
        "venueId": f"v-{booking_id}",
        "venueName": name,
        "status": status,
        "free": free,
        "suitable": suitable,
        "verdict": "suitable" if free and suitable else "not suitable",
        "reasons": [] if free and suitable else [f"{name} already has a confirmed booking at an overlapping time."],
        "startsAt": START.isoformat(),
        "endsAt": END.isoformat(),
        **extra,
    }


def reservation(reservation_id="rs-1", quantity=2, available=5, **extra):
    return {
        "reservationId": reservation_id,
        "equipmentId": "eq1",
        "equipmentName": "Projector",
        "quantity": quantity,
        "availableQuantity": available,
        "canMeet": quantity <= available,
        "shortfall": max(0, quantity - available),
        **extra,
    }


def applied(rows, carry=True):
    """What venue-service does on apply, for rows judged as `rows`."""
    out = []
    for row in rows:
        if row["status"] == "pending":
            out.append({**row, "outcome": "moved"})
        elif carry and row["free"] and row["suitable"]:
            out.append({**row, "outcome": "carried"})
        else:
            out.append({**row, "status": "cancelled", "outcome": "released"})
    return out


class RescheduleCase(EventCase):
    def setUp(self):
        super().setUp()
        self.venues = [venue()]
        self.equipment = [reservation()]
        self.patches = {
            "venue_preview": patch(
                "app.services.event_service.preview_venue_reschedule", side_effect=lambda *a: self.venues
            ),
            "equipment_preview": patch(
                "app.services.event_service.preview_equipment_reschedule", side_effect=lambda *a: self.equipment
            ),
            "venue_apply": patch(
                "app.services.event_service.reschedule_venues",
                side_effect=lambda event_id, s, e, reason, carry, auth: applied(self.venues, carry),
            ),
            "equipment_apply": patch(
                "app.services.event_service.reschedule_equipment",
                side_effect=lambda *a: [
                    {**row, "outcome": "moved" if row["canMeet"] else "flagged"} for row in self.equipment
                ],
            ),
            "publish": patch("app.services.event_service.publish_notification", return_value=True),
            "directory": patch(
                "app.services.event_service.users_with_roles",
                return_value={"venue-1": {"role": "venue"}, "tech-1": {"role": "techsupport"}},
            ),
            "attendees": patch(
                "app.services.event_service.registered_attendees",
                return_value=[{"userId": "att-1", "attendeeEmail": "amy@example.com"}],
            ),
            "inbox": patch("app.services.event_service.record_notification", return_value=True),
            "email": patch("app.services.event_service.send_notification", return_value=True),
            "names": patch("app.services.event_service.organisation_names", return_value={}),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}

    def tearDown(self):
        for p in self.patches.values():
            p.stop()
        super().tearDown()

    def event(self, status="planning", event_id="e1", **overrides):
        values = dict(
            eventName="Summit", coordinatorId="coord-1", proposedStartAt=START, proposedEndAt=END, registrationEnabled=False
        )
        values.update(overrides)
        return insert_event(self.db, eventId=event_id, status=status, **values)

    def move(self, event_id="e1", coordinator_id="coord-1", start=NEW_START, end=NEW_END, reason="Speaker moved", **kw):
        return self.service.reschedule(event_id, coordinator_id, start, end, reason, "Bearer token", **kw)

    def preview(self, event_id="e1", start=NEW_START, end=NEW_END, coordinator_id="coord-1"):
        return self.service.preview_reschedule(event_id, coordinator_id, start, end, "Bearer token")

    def refused(self, action, *args, **kwargs) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            action(*args, **kwargs)
        return ctx.exception

    def stored(self, event_id="e1") -> Event:
        self.db.expire_all()
        return self.db.get(Event, event_id)


class TestWhoAndWhen(RescheduleCase):
    """AC1."""

    def test_approved_planning_and_confirmed_events_can_be_moved_with_a_reason(self):
        for index, status in enumerate(("approved", "planning", "safety approved", "preparing", "confirmed", "reconsidering")):
            self.event(status, event_id=f"e{index}")

            moved = self.move(f"e{index}")

            self.assertEqual((moved.proposedStartAt, moved.proposedEndAt), (NEW_START, NEW_END), status)
            self.assertEqual(moved.rescheduleReason, "Speaker moved")
            self.assertEqual((moved.previousStartAt, moved.previousEndAt), (START, END))

    def test_other_stages_are_refused(self):
        for index, status in enumerate(("submitted", "under review", "completed", "cancelled", "rejected")):
            self.event(status, event_id=f"x{index}")

            self.assertEqual(self.refused(self.move, f"x{index}").status_code, 409, status)
        self.mocks["venue_apply"].assert_not_called()

    def test_only_the_assigned_coordinator(self):
        self.event()
        self.event(event_id="e-none", coordinatorId=None)

        self.assertEqual(self.refused(self.move, coordinator_id="coord-2").status_code, 403)
        self.assertEqual(self.refused(self.preview, coordinator_id="coord-2").status_code, 403)
        self.assertEqual(self.refused(self.move, "e-none").status_code, 409)

    def test_the_new_period_must_be_real_and_ahead(self):
        self.event()

        self.assertEqual(self.refused(self.move, end=NEW_START).status_code, 422)
        self.assertEqual(self.refused(self.move, start=datetime.utcnow() - DAY, end=NEW_END).status_code, 422)
        self.assertEqual(self.refused(self.move, start=START, end=END).status_code, 409)
        self.assertEqual(self.refused(self.move, reason="   ").status_code, 422)
        self.assertEqual(self.stored().proposedStartAt, START)

    def test_the_request_needs_a_reason(self):
        with self.assertRaises(ValueError):
            RescheduleIn(proposedStartAt=NEW_START, proposedEndAt=NEW_END, reason="  ")
        offset = RescheduleIn(proposedStartAt="2027-01-05T10:00:00+08:00", proposedEndAt="2027-01-05T12:00:00+08:00", reason="x")
        self.assertEqual(offset.proposedStartAt, datetime(2027, 1, 5, 2, 0))


class TestPreview(RescheduleCase):
    """AC2 and AC5: what would happen, with nothing moved."""

    def test_each_booked_venue_and_reservation_is_judged_at_the_new_time(self):
        self.event()
        self.venues = [venue(), venue("vb-2", "Exhibition Hall B", free=False), venue("vb-3", "Studio", status="pending")]
        self.equipment = [reservation(), reservation("rs-2", quantity=4, available=1)]

        preview = self.preview()

        self.assertEqual((preview.venueFree, preview.venueSuitable), (False, True))
        self.assertEqual(preview.unavailableVenues, ["Exhibition Hall B"])
        self.assertFalse(preview.equipmentAvailable)
        self.assertEqual([line.shortfall for line in preview.equipment], [0, 3])
        self.assertEqual((preview.currentStartAt, preview.proposedStartAt), (START, NEW_START))
        self.assertTrue(any("Marina Hall A is free and suitable" in line for line in preview.messages))
        self.assertTrue(any("Exhibition Hall B is not available" in line for line in preview.messages))
        self.assertTrue(any("Studio" in line and "waiting for Venue Staff" in line for line in preview.messages))
        self.assertTrue(any("only 1 free" in line for line in preview.messages))
        # AC5: nothing is applied or saved.
        self.mocks["venue_apply"].assert_not_called()
        self.mocks["equipment_apply"].assert_not_called()
        self.assertEqual(self.stored().proposedStartAt, START)

    def test_an_event_with_no_booked_venue_has_nothing_to_judge(self):
        self.event()
        self.venues = [venue(status="pending")]
        self.equipment = []

        preview = self.preview()

        self.assertEqual((preview.venueFree, preview.venueSuitable, preview.equipmentAvailable), (None, None, True))
        self.assertEqual(preview.unavailableVenues, [])


class TestVenues(RescheduleCase):
    """AC3 and AC4."""

    def test_a_free_and_suitable_venue_is_carried_across(self):
        self.event()

        moved = self.move()

        self.assertTrue(moved.venueCarried)
        self.assertEqual(moved.venues[0].outcome, "carried")
        self.assertEqual(self.mocks["venue_apply"].call_args.args[1:5], (NEW_START, NEW_END, "Speaker moved", True))
        self.assertTrue(any("carried across" in line for line in moved.messages))

    def test_an_unavailable_venue_is_named_before_anything_is_committed(self):
        self.event()
        self.venues = [venue(), venue("vb-2", "Exhibition Hall B", suitable=False)]

        refused = self.refused(self.move)

        self.assertEqual(refused.status_code, 409)
        self.assertTrue(refused.detail["requiresConfirmation"])
        self.assertIn("Exhibition Hall B is not available", refused.detail["message"])
        self.assertEqual([row["venueName"] for row in refused.detail["unavailableVenues"]], ["Exhibition Hall B"])
        # Abandoning: nothing moved, nothing saved.
        self.mocks["venue_apply"].assert_not_called()
        self.mocks["equipment_apply"].assert_not_called()
        self.assertEqual(self.stored().proposedStartAt, START)

    def test_rescheduling_anyway_releases_only_the_unavailable_venue(self):
        self.event()
        self.venues = [venue(), venue("vb-2", "Exhibition Hall B", free=False)]

        moved = self.move(confirm_venue_unavailable=True)

        self.assertEqual([row.outcome for row in moved.venues], ["carried", "released"])
        self.assertEqual(moved.releasedVenues, ["Exhibition Hall B"])
        self.assertTrue(any("Exhibition Hall B was released" in line and "Search for another venue" in line for line in moved.messages))

    def test_choosing_not_to_carry_releases_every_booked_venue(self):
        self.event()

        moved = self.move(carry_venue=False)

        self.assertFalse(moved.venueCarried)
        self.assertEqual(moved.releasedVenues, ["Marina Hall A"])
        self.assertFalse(self.mocks["venue_apply"].call_args.args[4])

    def test_a_venue_taken_meanwhile_stops_the_reschedule(self):
        self.event()
        self.mocks["venue_apply"].side_effect = HTTPException(status_code=409, detail="taken")

        self.assertEqual(self.refused(self.move).status_code, 409)
        self.mocks["equipment_apply"].assert_not_called()
        self.assertEqual(self.stored().proposedStartAt, START)

    def test_unreachable_venue_service_stops_the_reschedule(self):
        self.event()
        self.mocks["venue_preview"].side_effect = service_unavailable("down")

        self.assertEqual(self.refused(self.move).status_code, 503)
        self.assertEqual(self.refused(self.preview).status_code, 503)
        self.assertEqual(self.stored().proposedStartAt, START)


class TestEquipment(RescheduleCase):
    """AC6."""

    def test_reservations_that_cannot_be_met_are_flagged_not_dropped(self):
        self.event()
        self.equipment = [reservation(), reservation("rs-2", quantity=4, available=1)]

        moved = self.move()

        self.assertEqual([line.outcome for line in moved.equipment], ["moved", "flagged"])
        self.assertTrue(moved.equipmentChecked)
        self.assertTrue(any("4 × Projector: only 1 free" in line for line in moved.messages))

    def test_unreachable_equipment_service_still_moves_the_event_and_says_so(self):
        self.event()
        self.mocks["equipment_apply"].side_effect = service_unavailable("down")

        moved = self.move()

        self.assertFalse(moved.equipmentChecked)
        self.assertEqual(self.stored().proposedStartAt, NEW_START)
        self.assertTrue(any("technical support" in line for line in moved.messages))


class TestNotices(RescheduleCase):
    """AC7."""

    def test_the_organiser_venue_staff_technical_support_and_attendees_are_told(self):
        self.event()

        moved = self.move()

        call = self.mocks["publish"].call_args
        self.assertEqual(call.args[0], "event.rescheduled")
        self.assertEqual(
            {(row["userId"], row["role"]) for row in call.args[3]},
            {("org-1", "organiser"), ("venue-1", "venue"), ("tech-1", "techsupport")},
        )
        self.assertEqual(call.args[4]["reason"], "Speaker moved")
        self.assertIn("SGT", call.args[4]["newPeriod"])
        self.assertEqual(call.kwargs["actor_id"], "coord-1")
        self.assertEqual(moved.notifiedAttendees, 1)
        title, body = self.mocks["inbox"].call_args.args[3:5]
        self.assertIn("new date or time", title)
        self.mocks["email"].assert_called_once()

    def test_a_failed_notice_does_not_undo_the_reschedule(self):
        self.event()
        self.mocks["publish"].return_value = False
        self.mocks["attendees"].side_effect = RuntimeError("down")

        self.move()

        self.assertEqual(self.stored().proposedStartAt, NEW_START)


class TestRegistration(RescheduleCase):
    """AC8."""

    def test_a_close_after_the_new_start_is_brought_forward_and_the_coordinator_told(self):
        earlier = START - 5 * DAY
        self.event(registrationEnabled=True, registrationOpensAt=START - 20 * DAY, registrationClosesAt=START - DAY)

        preview = self.preview(start=earlier, end=earlier + timedelta(hours=2))
        moved = self.move(start=earlier, end=earlier + timedelta(hours=2))

        self.assertTrue(preview.registrationCloseAdjusted)
        self.assertEqual(preview.registrationClosesAt, earlier)
        self.assertTrue(moved.registrationCloseAdjusted)
        self.assertEqual((moved.registrationClosesAt, moved.previousRegistrationClosesAt), (earlier, START - DAY))
        self.assertTrue(any("Registration closed" in line and "now closes at the new start" in line for line in moved.messages))

    def test_a_close_before_the_new_start_stays(self):
        self.event(registrationEnabled=True, registrationOpensAt=START - 20 * DAY, registrationClosesAt=START - DAY)

        moved = self.move()

        self.assertFalse(moved.registrationCloseAdjusted)
        self.assertEqual(moved.registrationClosesAt, START - DAY)

    def test_a_window_that_would_open_after_the_new_start_must_change_first(self):
        earlier = START - 10 * DAY
        self.event(registrationEnabled=True, registrationOpensAt=START - 5 * DAY, registrationClosesAt=START - DAY)

        refused = self.refused(self.move, start=earlier, end=earlier + timedelta(hours=2))

        self.assertEqual(refused.status_code, 409)
        self.assertIn("Change the registration period first", refused.detail)
        self.mocks["venue_apply"].assert_not_called()


class TestStatusAndLog(RescheduleCase):
    """AC9, and SPM-71's rule for a significant change."""

    def test_the_move_old_and_new_period_reason_actor_and_time_are_logged(self):
        self.event()

        self.move()

        log = self.service.get_activity_log("e1")
        entry = next(row for row in log if row.kind == "reschedule")
        self.assertEqual((entry.changedBy, entry.note, entry.field), ("coord-1", "Speaker moved", "schedule"))
        self.assertIn("SGT", entry.oldValue)
        self.assertNotEqual(entry.oldValue, entry.newValue)
        self.assertEqual({row.field for row in log if row.kind == "edit"}, {"proposedStartAt", "proposedEndAt"})
        self.assertIn("Speaker moved", log[-1].note)

    def test_a_confirmed_event_reads_as_reconsidering_until_re_confirmed(self):
        self.event("confirmed")

        moved = self.move()

        self.assertEqual(moved.status, "reconsidering")
        change = self.db.query(EventStatusHistory).filter_by(eventId="e1").one()
        self.assertIn("Rescheduled from", change.note)
        self.assertIn("Reason: Speaker moved", change.note)
        log = self.service.get_activity_log("e1")
        self.assertEqual([row.kind for row in log][-2:], ["reschedule", "status"])

    def test_a_safety_approval_is_withdrawn(self):
        self.event("safety approved")
        self.db.add(
            EventSafetyReview(
                reviewId="sr-1", eventId="e1", status="approved", submittedBy="coord-1",
                submittedAt=datetime.utcnow(), crowdMovement="x", equipmentPlacement="", package={},
            )
        )
        self.db.commit()

        moved = self.move()

        self.assertEqual(moved.status, "planning")

    def test_a_planning_event_stays_in_planning(self):
        self.event()

        self.assertEqual(self.move().status, "planning")


class TestRescheduleRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_service.organisation_names", return_value={}),
            patch("app.services.event_service.preview_venue_reschedule", return_value=[venue()]),
            patch("app.services.event_service.preview_equipment_reschedule", return_value=[reservation()]),
            patch("app.services.event_service.reschedule_venues", return_value=applied([venue()])),
            patch("app.services.event_service.reschedule_equipment", return_value=[{**reservation(), "outcome": "moved"}]),
            patch("app.services.event_service.publish_notification", return_value=True),
            patch("app.services.event_service.users_with_roles", return_value={}),
            patch("app.services.event_service.registered_attendees", return_value=[]),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch("app.routers.event.resolve_caller", return_value={"userId": "coord-1", "role": "coordinator"})
        self.caller_mock = self.caller.start()
        self.reminder = patch.object(EventReminders, "run_for_event", return_value=None)
        self.reminder_mock = self.reminder.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.reminder.stop()
        self.caller.stop()
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_preview_then_reschedule(self):
        insert_event(self.db, eventId="e1", status="planning", coordinatorId="coord-1", proposedStartAt=START, proposedEndAt=END)
        period = {"proposedStartAt": NEW_START.isoformat() + "Z", "proposedEndAt": NEW_END.isoformat() + "Z"}

        preview = self.client.post("/events/e1/reschedule/preview", headers=HEADERS, json=period)
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})
        blank = self.client.post("/events/e1/reschedule", headers=HEADERS, json={**period, "reason": " "})
        moved = self.client.post(
            "/events/e1/reschedule", headers=HEADERS, json={**period, "reason": "Client asked", "carryVenueBooking": True}
        )

        self.assertEqual(preview.status_code, 200)
        self.assertEqual((preview.json()["venueFree"], preview.json()["equipmentAvailable"]), (True, True))
        self.assertEqual(blank.status_code, 422)
        self.assertEqual(moved.status_code, 200, moved.json())
        self.assertEqual((moved.json()["rescheduleReason"], moved.json()["venueCarried"]), ("Client asked", True))
        self.reminder_mock.assert_called_once_with("e1")
        log = self.client.get("/events/e1/activity-log", headers=HEADERS).json()
        self.assertEqual(log[-1]["kind"], "reschedule")

    def test_a_reminder_failure_does_not_fail_the_reschedule(self):
        insert_event(self.db, eventId="e1", status="planning", coordinatorId="coord-1", proposedStartAt=START, proposedEndAt=END)
        self.reminder_mock.side_effect = RuntimeError("down")

        moved = self.client.post(
            "/events/e1/reschedule",
            headers=HEADERS,
            json={"proposedStartAt": NEW_START.isoformat(), "proposedEndAt": NEW_END.isoformat(), "reason": "x"},
        )

        self.assertEqual(moved.status_code, 200)


class TestReminderFollowsTheNewDate(EventCase):
    """AC10: the approaching-event reminder follows the new date at once."""

    def setUp(self):
        super().setUp()
        self.patches = [
            patch("app.services.reminders.arrangement_inputs", return_value=([], [], {})),
            patch("app.services.reminders.users_with_roles", return_value={}),
        ]
        for p in self.patches:
            p.start()
        self.sent = patch("app.services.reminders.publish_notification", return_value=True)
        self.publish = self.sent.start()

    def tearDown(self):
        self.sent.stop()
        for p in self.patches:
            p.stop()
        super().tearDown()

    def test_an_event_moved_inside_the_lead_time_is_reminded_for_its_new_date(self):
        now = datetime(2026, 11, 1, 9)
        insert_event(
            self.db, eventId="e1", status="planning", coordinatorId="coord-1",
            proposedStartAt=now + 3 * DAY, proposedEndAt=now + 3 * DAY + timedelta(hours=2),
        )

        outcome = EventReminders(self.db).run_for_event("e1", now)

        self.assertEqual(outcome.sent, ["readiness.reminder"])
        occurrence, context = self.publish.call_args.args[2], self.publish.call_args.args[4]
        self.assertTrue(occurrence.endswith("20261104"))
        self.assertEqual(context["eventDate"], "04 Nov 2026")

    def test_an_event_outside_the_lead_time_or_closed_is_not_checked(self):
        now = datetime(2026, 11, 1, 9)
        insert_event(self.db, eventId="far", status="planning", proposedStartAt=now + 20 * DAY, proposedEndAt=now + 21 * DAY)
        insert_event(self.db, eventId="done", status="completed", proposedStartAt=now + DAY, proposedEndAt=now + 2 * DAY)

        reminders = EventReminders(self.db)

        self.assertIsNone(reminders.run_for_event("far", now))
        self.assertIsNone(reminders.run_for_event("done", now))
        self.assertIsNone(reminders.run_for_event("missing", now))
        self.publish.assert_not_called()
