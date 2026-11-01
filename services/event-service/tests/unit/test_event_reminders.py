from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.dao.event_dao import EventDAO
from app.main import app
from app.models.event_readiness import EventReadinessItem
from app.orchestration import clients
from app.services.event_followup import EventFollowUp
from app.services.reminders import EventReminders
from shared.testing.cases import ServiceTestCase
from tests.unit.support import EventCase, insert_event

NOW = datetime(2026, 10, 15, 9, 0)
NOTHING = ([], [], {})
READY = ([{"status": "complete", "quantity": 1, "reviewNote": ""}], [], {"venueName": "Marina Hall A"})
VENUE_ONLY_OUTSTANDING = ([{"status": "complete", "quantity": 1, "reviewNote": ""}], [], {})
EQUIPMENT_ONLY_OUTSTANDING = ([], [], {"venueName": "Marina Hall A"})
DIRECTORY = {
    "venue-1": {"userId": "venue-1", "role": "venue"},
    "tech-1": {"userId": "tech-1", "role": "techsupport"},
    "lead-1": {"userId": "lead-1", "role": "coordinatorlead"},
}


def event_in(db, days, **overrides):
    start = NOW + timedelta(days=days)
    data = dict(
        eventId=f"e-{days}",
        eventName="AI in Events Summit",
        status="planning",
        coordinatorId="coord-1",
        proposedStartAt=start,
        proposedEndAt=start + timedelta(hours=4),
    )
    data.update(overrides)
    return insert_event(db, **data)


class ReminderCase(EventCase):
    def setUp(self):
        super().setUp()
        self.inputs = {}
        self.read = patch(
            "app.services.reminders.arrangement_inputs", side_effect=lambda event_id: self.inputs.get(event_id, NOTHING)
        )
        self.read.start()
        self.directory = patch("app.services.reminders.users_with_roles", return_value=DIRECTORY)
        self.directory.start()
        self.sent = patch("app.services.reminders.publish_notification", return_value=True)
        self.publish = self.sent.start()
        self.holds = patch("app.services.reminders.expired_holds", return_value=[])
        self.expired = self.holds.start()
        self.reminders = EventReminders(self.db)

    def tearDown(self):
        self.holds.stop()
        self.sent.stop()
        self.directory.stop()
        self.read.stop()
        super().tearDown()

    def triggers(self):
        return [call.args[0] for call in self.publish.call_args_list]

    def recipients(self, trigger):
        return [
            [row["userId"] for row in call.args[3]] for call in self.publish.call_args_list if call.args[0] == trigger
        ]


class TestSelection(ReminderCase):
    def test_only_events_inside_the_lead_time_that_are_open_and_not_ready_are_reminded(self):
        event_in(self.db, 3)  # inside the lead time, nothing arranged
        event_in(self.db, 2, eventId="e-ready")
        self.inputs["e-ready"] = READY
        event_in(self.db, 20, eventId="e-far")
        event_in(self.db, -1, eventId="e-past")
        for status in ("completed", "cancelled", "rejected"):
            event_in(self.db, 3, eventId=f"e-{status}", status=status)

        result = self.reminders.run(NOW)

        self.assertEqual(result.checked, 2)
        self.assertEqual([row.eventId for row in result.reminded], ["e-3"])
        self.assertEqual(result.leadDays, 7)
        self.assertEqual(result.ranAt, NOW)

    def test_the_lead_time_is_read_from_settings(self):
        event_in(self.db, 3)

        with patch.object(settings, "event_reminder_lead_days", 2):
            self.assertEqual(self.reminders.run(NOW).checked, 0)
        with patch.object(settings, "event_reminder_lead_days", 3):
            self.assertEqual(self.reminders.run(NOW).checked, 1)

    def test_it_runs_from_the_clock_when_no_time_is_given(self):
        insert_event(
            self.db,
            eventId="e-soon",
            status="planning",
            coordinatorId="coord-1",
            proposedStartAt=datetime.utcnow() + timedelta(days=1),
            proposedEndAt=datetime.utcnow() + timedelta(days=1, hours=4),
        )

        self.assertEqual([row.eventId for row in self.reminders.run().reminded], ["e-soon"])

    def test_an_event_whose_arrangements_cannot_be_read_is_skipped_not_reminded(self):
        event_in(self.db, 3)
        self.read.stop()
        self.read = patch("app.services.reminders.arrangement_inputs", return_value=None)
        self.read.start()

        result = self.reminders.run(NOW)

        self.assertEqual(result.reminded, [])
        self.assertEqual([(row.eventId, row.reason) for row in result.skipped], [("e-3", "Its arrangements could not be read")])
        self.publish.assert_not_called()

    def test_an_event_that_is_fully_ready_is_not_reminded(self):
        event_in(self.db, 3)
        self.inputs["e-3"] = READY

        result = self.reminders.run(NOW)

        self.assertEqual((result.checked, result.reminded), (1, []))
        self.publish.assert_not_called()


class TestWhoIsTold(ReminderCase):
    def test_the_assigned_coordinator_is_told_the_event_the_date_and_what_is_outstanding(self):
        event_in(self.db, 3)

        self.reminders.run(NOW)

        trigger, event_id, _occurrence, recipients, context = self.publish.call_args_list[0].args
        self.assertEqual((trigger, event_id), ("readiness.reminder", "e-3"))
        self.assertEqual(recipients, [{"userId": "coord-1", "role": "coordinator"}])
        self.assertEqual(
            context,
            {
                "eventName": "AI in Events Summit",
                "eventDate": "18 Oct 2026",
                "outstanding": "Venue (outstanding), Equipment (outstanding)",
            },
        )

    def test_the_event_date_is_the_singapore_date(self):
        # 17:00 UTC on 18 Oct is 01:00 on 19 Oct in Singapore.
        event_in(self.db, 3, proposedStartAt=datetime(2026, 10, 18, 17, 0), proposedEndAt=datetime(2026, 10, 18, 19, 0))

        self.reminders.run(NOW)

        self.assertEqual(self.publish.call_args_list[0].args[4]["eventDate"], "19 Oct 2026")

    def test_an_outstanding_venue_also_tells_venue_staff_and_outstanding_equipment_tells_technical_support(self):
        event_in(self.db, 3)
        self.reminders.run(NOW)
        self.assertEqual(
            self.triggers(),
            ["readiness.reminder", "readiness.reminder.venue", "readiness.reminder.equipment"],
        )
        self.assertEqual(self.recipients("readiness.reminder.venue"), [["venue-1"]])
        self.assertEqual(self.recipients("readiness.reminder.equipment"), [["tech-1"]])

    def test_a_line_that_is_not_outstanding_tells_nobody_who_could_not_act_on_it(self):
        event_in(self.db, 3)
        self.inputs["e-3"] = EQUIPMENT_ONLY_OUTSTANDING
        self.reminders.run(NOW)
        self.assertEqual(self.triggers(), ["readiness.reminder", "readiness.reminder.equipment"])

        self.publish.reset_mock()
        self.inputs["e-3"] = VENUE_ONLY_OUTSTANDING
        self.reminders.run(NOW)
        self.assertEqual(self.triggers(), ["readiness.reminder", "readiness.reminder.venue"])

    def test_an_approaching_event_with_no_coordinator_goes_to_the_coordinator_lead(self):
        event_in(self.db, 3, coordinatorId=None)

        result = self.reminders.run(NOW)

        self.assertNotIn("readiness.reminder", self.triggers())
        self.assertEqual(self.recipients("readiness.reminder.unassigned"), [["lead-1"]])
        self.assertIsNone(result.reminded[0].coordinatorId)
        self.assertIn("readiness.reminder.unassigned", result.reminded[0].sent)

    def test_a_stored_line_counts_and_a_stored_line_stands_in_for_the_derived_one(self):
        event_in(self.db, 3)
        self.inputs["e-3"] = READY
        self.db.add(EventReadinessItem(itemId="i1", eventId="e-3", category="Catering", status="in_progress"))
        self.db.add(EventReadinessItem(itemId="derived-venue", eventId="e-3", category="venue", status="confirmed"))
        self.db.add(EventReadinessItem(itemId="i2", eventId="e-3", category="Signage", status="confirmed"))
        self.db.commit()

        result = self.reminders.run(NOW)

        self.assertEqual(self.triggers(), ["readiness.reminder"])
        self.assertEqual(self.publish.call_args_list[0].args[4]["outstanding"], "Catering (in progress)")
        self.assertEqual([(row.category, row.status) for row in result.reminded[0].outstanding], [("Catering", "in_progress")])

    def test_staff_are_skipped_when_the_directory_cannot_be_read_but_the_coordinator_is_still_told(self):
        event_in(self.db, 3)
        self.directory.stop()
        self.directory = patch("app.services.reminders.users_with_roles", return_value=None)
        self.directory.start()

        result = self.reminders.run(NOW)

        self.assertEqual(self.triggers(), ["readiness.reminder"])
        self.assertEqual(result.reminded[0].sent, ["readiness.reminder"])

    def test_a_reminder_notification_service_refuses_is_reported_as_failed(self):
        event_in(self.db, 3)
        self.publish.return_value = False

        result = self.reminders.run(NOW)

        self.assertEqual(result.reminded[0].sent, [])
        self.assertEqual(
            result.reminded[0].failed,
            ["readiness.reminder", "readiness.reminder.venue", "readiness.reminder.equipment"],
        )


class TestOncePerOccasion(ReminderCase):
    def test_the_occurrence_is_the_same_on_every_run_so_a_repeat_notifies_nobody_twice(self):
        event_in(self.db, 3)

        self.reminders.run(NOW)
        self.reminders.run(NOW + timedelta(days=1))

        occurrences = [call.args[2] for call in self.publish.call_args_list]
        half = len(occurrences) // 2
        self.assertEqual(occurrences[:half], occurrences[half:])
        self.assertIn("e-3:readiness.reminder:20261018", occurrences)

    def test_a_new_start_date_is_a_new_occasion(self):
        event = event_in(self.db, 3)
        self.reminders.run(NOW)
        event.proposedStartAt = NOW + timedelta(days=4)
        self.db.commit()
        self.reminders.run(NOW)

        coordinator = [call.args[2] for call in self.publish.call_args_list if call.args[0] == "readiness.reminder"]
        self.assertEqual(coordinator, ["e-3:readiness.reminder:20261018", "e-3:readiness.reminder:20261019"])


class TestApproachingQuery(ReminderCase):
    def test_it_returns_events_starting_in_the_window_soonest_first_and_leaves_out_excluded_statuses(self):
        event_in(self.db, 5)
        event_in(self.db, 1)
        event_in(self.db, 2, eventId="e-closed", status="completed")

        rows = EventDAO(self.db).list_approaching(NOW, NOW + timedelta(days=7), ["completed"])

        self.assertEqual([row.eventId for row in rows], ["e-1", "e-5"])


class TestNotReady(ReminderCase):
    def test_what_the_readiness_view_shows_as_not_ready_for_an_event_with_nothing_stored(self):
        pending = EventFollowUp(self.db).not_ready("e-none", *NOTHING)

        self.assertEqual(pending, [{"category": "venue", "status": "outstanding"}, {"category": "equipment", "status": "outstanding"}])

    def test_equipment_needing_attention_is_not_ready(self):
        short = [{"status": "partial", "quantity": 2, "reviewNote": ""}]

        pending = EventFollowUp(self.db).not_ready("e-none", short, [], {"venueName": "Marina Hall A"})

        self.assertEqual(pending, [{"category": "equipment", "status": "needs attention"}])


class TestDueSoonAlerts(ReminderCase):
    """SPM-5 AC8: a readiness line item nearing its due date alerts the coordinator."""

    def item(self, item_id, event_id, due_in, status="outstanding"):
        self.db.add(
            EventReadinessItem(
                itemId=item_id,
                eventId=event_id,
                category="Catering",
                status=status,
                dueAt=NOW + due_in,
                assignedAt=NOW - timedelta(days=5),
            )
        )
        self.db.commit()

    def alerts(self):
        return [call for call in self.publish.call_args_list if call.args[0] == "readiness.due_soon"]

    def test_an_item_due_within_three_days_alerts_the_assigned_coordinator_once_per_due_date(self):
        event_in(self.db, 30)  # beyond the event lead time, so only the item is due soon
        self.item("i-soon", "e-30", timedelta(days=2))

        result = self.reminders.run(NOW)

        self.assertEqual(result.dueSoonItems, ["i-soon"])
        (alert,) = self.alerts()
        trigger, event_id, occurrence, recipients, context = alert.args
        self.assertEqual(occurrence, "e-30:readiness.due_soon:i-soon:202610170900")
        self.assertEqual(recipients, [{"userId": "coord-1", "role": "coordinator"}])
        self.assertEqual(
            context,
            {"eventName": "AI in Events Summit", "category": "Catering", "dueDate": "17 Oct 2026 17:00 SGT", "status": "outstanding"},
        )

    def test_an_unassigned_event_alerts_the_lead(self):
        event_in(self.db, 30, coordinatorId=None)
        self.item("i-lead", "e-30", timedelta(hours=6), status="in_progress")

        self.reminders.run(NOW)

        (alert,) = self.alerts()
        self.assertEqual(alert.args[3], [{"userId": "lead-1", "role": "coordinatorlead"}])
        self.assertEqual(alert.args[4]["status"], "in progress")

    def test_ready_late_far_off_and_closed_items_alert_nobody(self):
        event_in(self.db, 30)
        event_in(self.db, 31, status="cancelled")
        self.item("i-ready", "e-30", timedelta(days=1), status="ready")
        self.item("i-late", "e-30", -timedelta(hours=1))
        self.item("i-far", "e-30", timedelta(days=4))
        self.item("i-closed", "e-31", timedelta(days=1))
        self.item("i-orphan", "e-gone", timedelta(days=1))

        self.assertEqual(self.reminders.run(NOW).dueSoonItems, [])
        self.assertEqual(self.alerts(), [])

    def test_an_alert_notification_service_refused_is_not_listed(self):
        event_in(self.db, 30)
        self.item("i-soon", "e-30", timedelta(days=2))
        self.publish.return_value = False

        self.assertEqual(self.reminders.run(NOW).dueSoonItems, [])


class TestExpiredHolds(ReminderCase):
    """SPM-93 AC4: the coordinator hears when a tentative hold runs out."""

    def held(self, booking_id="b1", event_id="e-30", expires=NOW - timedelta(hours=3)):
        return {"bookingId": booking_id, "eventId": event_id, "venueName": "Marina Hall A", "expiresAt": expires.isoformat()}

    def notices(self):
        return [call for call in self.publish.call_args_list if call.args[0] == "hold.expired"]

    def test_an_expired_hold_tells_the_coordinator_once_per_booking_and_expiry(self):
        event_in(self.db, 30)
        self.expired.return_value = [self.held()]

        result = self.reminders.run(NOW)

        self.assertEqual(result.expiredHolds, ["b1"])
        self.assertEqual(self.expired.call_args.args, (NOW - timedelta(days=2), NOW))
        (notice,) = self.notices()
        trigger, event_id, occurrence, recipients, context = notice.args
        self.assertEqual(occurrence, "e-30:hold.expired:b1:202610150600")
        self.assertEqual(recipients, [{"userId": "coord-1", "role": "coordinator"}])
        self.assertEqual(
            context, {"eventName": "AI in Events Summit", "venueName": "Marina Hall A", "expiredAt": "15 Oct 2026 14:00 SGT"}
        )

    def test_closed_unassigned_or_unknown_events_and_refused_notices_are_not_listed(self):
        event_in(self.db, 30, status="cancelled")
        event_in(self.db, 31, coordinatorId=None)
        event_in(self.db, 32)
        self.expired.return_value = [
            self.held("b-closed", "e-30"),
            self.held("b-nobody", "e-31"),
            self.held("b-gone", "e-gone"),
            self.held("b-refused", "e-32"),
        ]
        self.publish.return_value = False

        self.assertEqual(self.reminders.run(NOW).expiredHolds, [])
        self.assertEqual([call.args[2] for call in self.notices()], ["e-32:hold.expired:b-refused:202610150600"])

    def test_venue_service_that_cannot_be_read_announces_nothing(self):
        self.expired.return_value = None

        self.assertEqual(self.reminders.run(NOW).expiredHolds, [])


class TestServiceCalls(ServiceTestCase):
    def get(self, response=None, error=None):
        mocked = MagicMock(return_value=response) if error is None else MagicMock(side_effect=error)
        return patch.object(clients.httpx, "get", mocked), mocked

    def test_it_reads_with_the_service_key_and_returns_the_body(self):
        patcher, mocked = self.get(MagicMock(status_code=200, json=lambda: {"ok": True}))
        with patcher, patch.object(settings, "internal_service_key", "key-1"):
            body = clients._service_get("http://x/y", {"a": 1})

        self.assertEqual(body, {"ok": True})
        self.assertEqual(mocked.call_args.kwargs["headers"], {"X-Service-Key": "key-1"})
        self.assertEqual(mocked.call_args.kwargs["params"], {"a": 1})

    def test_a_failure_or_a_refusal_is_none(self):
        patcher, _ = self.get(error=httpx.ConnectError("down"))
        with patcher:
            self.assertIsNone(clients._service_get("http://x/y"))
        patcher, _ = self.get(MagicMock(status_code=403))
        with patcher:
            self.assertIsNone(clients._service_get("http://x/y"))

    def test_arrangement_inputs_joins_equipment_and_venue(self):
        answers = [{"requests": [{"a": 1}], "reservations": [{"b": 2}]}, {"venueName": "Hall"}]
        with patch.object(clients, "_service_get", side_effect=answers) as called:
            inputs = clients.arrangement_inputs("e1")

        self.assertEqual(inputs, ([{"a": 1}], [{"b": 2}], {"venueName": "Hall"}))
        self.assertTrue(called.call_args_list[0].args[0].endswith("/internal/equipment/events/e1/arrangements"))
        self.assertTrue(called.call_args_list[1].args[0].endswith("/internal/venues/bookings/public-summary"))

    def test_arrangement_inputs_is_none_when_either_service_cannot_be_read(self):
        for answers in ([None, {"venueName": ""}], [{"requests": [], "reservations": []}, None]):
            with self.subTest(answers=answers), patch.object(clients, "_service_get", side_effect=answers):
                self.assertIsNone(clients.arrangement_inputs("e1"))

    def test_handoff_arrangements_reads_bookings_and_equipment_with_the_service_key(self):
        # SPM-120: Venue Staff and technical support each send a part they cannot read across.
        answers = [[{"bookingId": "b1"}], {"requests": [{"a": 1}], "reservations": [{"b": 2}]}]
        with patch.object(clients, "_service_get", side_effect=answers) as called:
            rows = clients.handoff_arrangements("e1")

        self.assertEqual(rows, ([{"bookingId": "b1"}], [{"a": 1}], [{"b": 2}]))
        self.assertTrue(called.call_args_list[0].args[0].endswith("/internal/venues/bookings"))
        self.assertEqual(called.call_args_list[0].args[1], {"eventId": "e1"})
        self.assertTrue(called.call_args_list[1].args[0].endswith("/internal/equipment/events/e1/arrangements"))

    def test_handoff_arrangements_that_cannot_be_read_are_a_503_not_nothing_arranged(self):
        for answers in ([None, {"requests": [], "reservations": []}], [[], None]):
            with self.subTest(answers=answers), patch.object(clients, "_service_get", side_effect=answers):
                with self.assertRaises(HTTPException) as ctx:
                    clients.handoff_arrangements("e1")
                self.assertEqual(ctx.exception.status_code, 503)

    def test_expired_holds_reads_the_period_with_the_service_key(self):
        since, until = datetime(2026, 10, 13, 9), datetime(2026, 10, 15, 9)
        with patch.object(clients, "_service_get", return_value=[{"bookingId": "b1"}]) as called:
            self.assertEqual(clients.expired_holds(since, until), [{"bookingId": "b1"}])
        self.assertTrue(called.call_args.args[0].endswith("/internal/venues/holds/expired"))
        self.assertEqual(called.call_args.args[1], {"since": "2026-10-13T09:00:00", "until": "2026-10-15T09:00:00"})
        with patch.object(clients, "_service_get", return_value=None):
            self.assertIsNone(clients.expired_holds(since, until))

    def test_venue_catalogue_options_reads_with_the_service_key(self):
        offered = {"layouts": ["Theatre"], "facilities": [], "accessibility": []}
        with patch.object(clients, "_service_get", return_value=offered) as called:
            self.assertEqual(clients.venue_catalogue_options(), offered)
        self.assertTrue(called.call_args.args[0].endswith("/internal/venues/catalogue-options"))
        with patch.object(clients, "_service_get", return_value=None):
            self.assertIsNone(clients.venue_catalogue_options())

    def test_users_with_roles_is_keyed_by_user_id_or_none(self):
        with patch.object(clients, "_service_get", return_value=[{"userId": "u1", "role": "venue"}]) as called:
            self.assertEqual(clients.users_with_roles(["venue", "techsupport"]), {"u1": {"userId": "u1", "role": "venue"}})
        self.assertEqual(called.call_args.args[1], {"roles": "venue,techsupport"})
        with patch.object(clients, "_service_get", return_value=None):
            self.assertIsNone(clients.users_with_roles(["venue"]))


class TestRunRoute(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.key = patch.object(settings, "internal_service_key", "key-1")
        self.key.start()
        self.directory = patch("app.services.reminders.users_with_roles", return_value=DIRECTORY)
        self.directory.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.directory.stop()
        self.key.stop()
        super().tearDown()

    def test_the_daily_job_runs_it_with_the_service_key_and_no_user_token(self):
        response = self.client.post("/events/reminders/run", headers={"X-Service-Key": "key-1"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body["leadDays"], body["checked"], body["reminded"], body["skipped"]), (7, 0, [], []))

    def test_a_wrong_service_key_is_refused_even_with_a_coordinators_token(self):
        response = self.client.post(
            "/events/reminders/run", headers={"X-Service-Key": "nope", "Authorization": "Bearer t"}
        )

        self.assertEqual(response.status_code, 403)

    def test_a_coordinator_or_the_lead_can_run_it_on_demand(self):
        with patch("app.routers.reminders.resolve_caller", return_value={"userId": "u1", "role": "coordinator"}) as who:
            response = self.client.post("/events/reminders/run", headers={"Authorization": "Bearer t"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(who.call_args.kwargs["allowed_roles"], {"coordinator", "coordinatorlead"})

    def test_someone_else_is_refused_and_so_is_a_call_with_no_credentials(self):
        with patch("app.routers.reminders.resolve_caller", side_effect=HTTPException(status_code=403, detail="no")):
            refused = self.client.post("/events/reminders/run", headers={"Authorization": "Bearer t"})
        anonymous = self.client.post("/events/reminders/run")

        self.assertEqual(refused.status_code, 403)
        self.assertEqual(anonymous.status_code, 401)

    def test_the_service_key_is_refused_when_none_is_configured(self):
        with patch.object(settings, "internal_service_key", ""):
            response = self.client.post("/events/reminders/run", headers={"X-Service-Key": ""})

        self.assertEqual(response.status_code, 403)
