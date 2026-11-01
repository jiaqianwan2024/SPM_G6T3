"""SPM-85: the assigned coordinator reviews and decides a change request."""

from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.event_field_change import EventFieldChange
from app.schemas.event import ChangeRequestCreate, ChangeRequestDecline
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import forbidden, service_unavailable
from shared.testing.cases import ServiceTestCase
from tests.unit.support import insert_event
from tests.unit.test_event_change_requests import (
    COORDINATOR,
    DIRECTORY,
    END,
    HEADERS,
    ORGANISER,
    START,
    VENUE,
    ChangeRequestCase,
)

BOOKING = {
    "bookingId": "vb-1",
    "venueId": "v1",
    "eventId": "e1",
    "status": "approved",
    "startsAt": "2026-12-01T09:00:00",
    "endsAt": "2026-12-01T17:00:00",
}
MARINA = {
    "venueId": "v1",
    "name": "Marina Hall A",
    "capacity": 300,
    "layouts": [{"name": "Theatre", "capacity": 200}, {"name": "Banquet", "capacity": 120}],
}
NOT_SUITABLE = {
    "eventId": "e1",
    "venueId": "v1",
    "verdict": "not suitable",
    "reasons": [{"severity": "failure", "check": "clash", "message": "Marina Hall A is booked by another event then."}],
}
PROJECTORS = {
    "reservationId": "rsv-1",
    "equipmentId": "eq1",
    "equipmentName": "Projector PX-200",
    "quantity": 2,
    "status": "active",
    "startsAt": "2026-12-01T09:00:00",
    "endsAt": "2026-12-01T17:00:00",
}
RELEASED_MICS = {**PROJECTORS, "reservationId": "rsv-2", "equipmentId": "eq2", "equipmentName": "Mic", "status": "released"}
ATTENDEE_ROW = {"userId": "att-1", "attendeeName": "Cara", "attendeeEmail": "cara@example.com", "status": "registered"}
LINE = {"equipmentId": "eq1", "quantity": 2, "technicalNotes": ""}


class ReviewCase(ChangeRequestCase):
    def setUp(self):
        super().setUp()
        clients = {
            "bookings": patch("app.services.event_service.confirmed_bookings", return_value=[BOOKING]),
            "venue": patch("app.services.event_service.venue_details", return_value=MARINA),
            "suitability": patch("app.services.event_service.venue_suitability", return_value=NOT_SUITABLE),
            "names": patch("app.services.event_service.equipment_names", return_value={"eq1": "Projector PX-200", "eq3": "Speaker"}),
            "reservations": patch(
                "app.services.event_service.equipment_reservations_for", return_value=[PROJECTORS, RELEASED_MICS]
            ),
            "free": patch("app.services.event_service.equipment_free", return_value=10),
            "attendees": patch("app.services.event_service.registered_attendees", return_value=[ATTENDEE_ROW]),
        }
        self.clients = {name: p.start() for name, p in clients.items()}
        self.patches.update({f"client-{name}": p for name, p in clients.items()})

    def assess(self, change_request_id, coordinator_id="coord-1"):
        return self.service.assess_change_request("e1", change_request_id, coordinator_id, "Bearer token")

    def assess_new(self, **changes):
        return self.assess(self.raise_(**changes).changeRequestId)

    def decline_narrower(self, change_request_id, reason="Only the attendance can change"):
        return self.service.decline_change_request(
            "e1", change_request_id, ChangeRequestDecline(reason=reason, askNarrower=True), "coord-1", "Bearer token"
        )

    def log(self):
        return self.service.get_activity_log("e1")


class TestCoordinatorSeesTheRequest(ReviewCase):
    """AC1."""

    def test_the_assigned_coordinator_sees_each_current_and_proposed_value_and_the_reason(self):
        self.event()
        self.raise_(reason="Client added a dinner", layoutPreference="Banquet", expectedAttendance=90)

        [listed] = self.service.list_change_requests("e1", COORDINATOR)

        self.assertEqual(listed.status, "pending")
        self.assertEqual(listed.currentValues, {"layoutPreference": "Theatre", "expectedAttendance": 50})
        self.assertEqual(listed.proposedChanges, {"layoutPreference": "Banquet", "expectedAttendance": 90})
        self.assertEqual(listed.reason, "Client added a dinner")


class TestImpactAssessment(ReviewCase):
    """AC2."""

    def test_a_move_names_every_booking_reservation_and_registration_it_affects(self):
        self.event()

        impact = self.assess_new(proposedStartAt=START + timedelta(days=7), proposedEndAt=END + timedelta(days=7))

        [booking] = impact.venueBookings
        self.assertEqual((booking.bookingId, booking.venueName), ("vb-1", "Marina Hall A"))
        # A released reservation no longer holds stock, so the change cannot affect it.
        self.assertEqual(
            [(row.reservationId, row.equipmentName, row.quantity) for row in impact.equipmentReservations],
            [("rsv-1", "Projector PX-200", 2)],
        )
        self.assertEqual([(row.attendeeName, row.attendeeEmail) for row in impact.registrations], [("Cara", "cara@example.com")])
        self.assertEqual(impact.unchecked, [])

    def test_only_the_arrangements_a_field_touches_are_read(self):
        self.event()
        cases = [
            ({"description": "New copy"}, ([], [], [])),
            ({"accessibilityNeeds": "Hearing loop"}, (["vb-1"], [], [])),
            ({"equipmentRequirements": "More mics"}, ([], ["rsv-1"], [])),
            ({"expectedAttendance": 80}, (["vb-1"], [], ["Cara"])),
        ]
        for proposed, expected in cases:
            with self.subTest(proposed=proposed):
                raised = self.raise_(**proposed)
                impact = self.assess(raised.changeRequestId)
                found = (
                    [row.bookingId for row in impact.venueBookings],
                    [row.reservationId for row in impact.equipmentReservations],
                    [row.attendeeName for row in impact.registrations],
                )
                self.assertEqual(found, expected)
                self.withdraw(raised.changeRequestId)

    def test_a_wording_change_reads_no_other_service(self):
        self.event()

        self.assess_new(eventName="Summit 2027")

        for name in ("bookings", "reservations", "attendees", "suitability", "free"):
            self.clients[name].assert_not_called()

    def test_a_part_that_cannot_be_read_is_named_and_the_rest_still_shown(self):
        self.clients["bookings"].side_effect = service_unavailable("down")
        self.event()

        impact = self.assess_new(proposedStartAt=START + timedelta(hours=1))

        self.assertEqual(impact.unchecked, ["venue"])
        self.assertEqual((impact.venueBookings, impact.venueSuitability), ([], None))
        self.assertEqual([row.reservationId for row in impact.equipmentReservations], ["rsv-1"])
        self.assertEqual(len(impact.registrations), 1)

    def test_any_other_refusal_is_passed_on_rather_than_called_unchecked(self):
        self.clients["bookings"].side_effect = forbidden("Not your event")
        self.event()
        raised = self.raise_(proposedStartAt=START + timedelta(hours=1))

        error = self.refused(self.assess, raised.changeRequestId)

        self.assertEqual((error.status_code, error.detail), (403, "Not your event"))

    def test_only_the_assigned_coordinator_and_only_while_pending(self):
        self.event()
        raised = self.raise_()

        self.assertEqual(self.refused(self.assess, raised.changeRequestId, coordinator_id="coord-2").status_code, 403)
        self.assertEqual(self.refused(self.assess, "missing").status_code, 404)
        self.decline(raised.changeRequestId)
        self.assertEqual(self.refused(self.assess, raised.changeRequestId).status_code, 409)

    def test_an_older_request_whose_values_cannot_be_read_is_refused(self):
        self.event()
        self.legacy_request({"proposedStartAt": "shifted earlier"})

        self.assertEqual(self.refused(self.assess, "cr-old").status_code, 422)

    def test_assessing_changes_nothing(self):
        self.event()
        raised = self.raise_(expectedAttendance=500)
        before = self.stored().model_dump()

        self.assess(raised.changeRequestId)

        self.assertEqual(self.stored().model_dump(), before)
        self.assertEqual(self.service.list_change_requests("e1", COORDINATOR)[0].status, "pending")
        self.mocks["flag"].assert_not_called()


class TestSuitabilityRerun(ReviewCase):
    """AC3."""

    def test_a_new_date_re_runs_each_booked_venue_at_the_proposed_values(self):
        self.event()

        impact = self.assess_new(proposedStartAt=START + timedelta(days=7), proposedEndAt=END + timedelta(days=7))

        [checked] = impact.venueSuitability
        self.assertEqual((checked.bookingId, checked.venueName, checked.verdict), ("vb-1", "Marina Hall A", "not suitable"))
        self.assertEqual(checked.reasons, ["Marina Hall A is booked by another event then."])
        self.clients["suitability"].assert_called_once_with(
            "e1",
            "v1",
            {"startsAt": "2026-12-08T09:00:00", "endsAt": "2026-12-08T17:00:00", "layout": "Theatre", "expectedAttendance": 50},
            "Bearer token",
        )

    def test_a_new_layout_or_time_alone_also_re_runs_it(self):
        self.event()
        for proposed, needs in (
            ({"layoutPreference": "Banquet"}, {"layout": "Banquet", "startsAt": "2026-12-01T09:00:00"}),
            ({"proposedEndAt": END + timedelta(hours=2)}, {"layout": "Theatre", "endsAt": "2026-12-01T19:00:00"}),
        ):
            with self.subTest(proposed=proposed):
                raised = self.raise_(**proposed)
                self.assertEqual(self.assess(raised.changeRequestId).venueSuitability[0].verdict, "not suitable")
                sent = self.clients["suitability"].call_args.args[2]
                self.assertEqual({key: sent[key] for key in needs}, needs)
                self.withdraw(raised.changeRequestId)

    def test_other_fields_leave_the_verdict_out(self):
        self.event()

        impact = self.assess_new(expectedAttendance=80, accessibilityNeeds="Hearing loop")

        self.assertIsNone(impact.venueSuitability)
        self.clients["suitability"].assert_not_called()

    def test_with_nothing_booked_there_is_nothing_to_judge(self):
        self.clients["bookings"].return_value = []
        self.event()

        self.assertEqual(self.assess_new(layoutPreference="Banquet").venueSuitability, [])


class TestCapacity(ReviewCase):
    """AC4."""

    def test_attendance_above_the_booked_layouts_capacity_names_both_figures(self):
        self.event()

        [row] = self.assess_new(expectedAttendance=500).capacity

        self.assertEqual(
            (row.venueName, row.layout, row.capacity, row.expectedAttendance, row.overCapacity),
            ("Marina Hall A", "Theatre", 200, 500, True),
        )

    def test_attendance_the_layout_holds_is_not_over(self):
        self.event()

        [row] = self.assess_new(expectedAttendance=200).capacity

        self.assertEqual((row.capacity, row.overCapacity), (200, False))

    def test_a_new_layout_is_judged_at_its_own_capacity(self):
        self.event(expectedAttendance=150)

        [row] = self.assess_new(layoutPreference="Banquet").capacity

        self.assertEqual((row.layout, row.capacity, row.expectedAttendance, row.overCapacity), ("Banquet", 120, 150, True))

    def test_a_layout_the_venue_does_not_offer_uses_its_largest_capacity(self):
        self.event()

        [row] = self.assess_new(layoutPreference="Cabaret").capacity

        self.assertEqual((row.layout, row.capacity), (None, 300))

    def test_a_date_change_alone_does_not_compare_capacity(self):
        self.event()

        self.assertIsNone(self.assess_new(proposedStartAt=START + timedelta(hours=1)).capacity)


class TestEquipmentQuantities(ReviewCase):
    """AC5."""

    def test_an_organiser_can_ask_for_different_quantities(self):
        self.event(equipmentLines=[LINE])

        raised = self.raise_(equipmentLines=[{"equipmentId": "eq1", "quantity": 5}])

        self.assertEqual(raised.proposedChanges, {"equipmentLines": [{"equipmentId": "eq1", "quantity": 5, "technicalNotes": ""}]})
        self.assertEqual(raised.currentValues, {"equipmentLines": [LINE]})
        self.assertTrue(raised.affectsEquipment)
        self.withdraw(raised.changeRequestId)
        error = self.refused(self.raise_, equipmentLines=[{"equipmentId": "eq1", "quantity": 2}])
        self.assertEqual(error.status_code, 422)

    def test_a_quantity_must_be_a_whole_number_of_at_least_one(self):
        for lines in ([{"equipmentId": "eq1", "quantity": 0}], [{"equipmentId": "eq1", "quantity": 1.5}], None):
            with self.subTest(lines=lines), self.assertRaises(ValidationError):
                ChangeRequestCreate(reason="r", proposedChanges={"equipmentLines": lines})

    def test_a_raise_the_free_units_cover_is_available(self):
        self.clients["free"].return_value = 3
        self.event(equipmentLines=[LINE])

        impact = self.assess_new(equipmentLines=[{"equipmentId": "eq1", "quantity": 5}])

        [line] = impact.equipmentAvailability
        self.assertEqual(
            (line.equipmentName, line.currentQuantity, line.proposedQuantity, line.extraQuantity),
            ("Projector PX-200", 2, 5, 3),
        )
        # The two already reserved for the event count toward the five.
        self.assertEqual((line.heldQuantity, line.freeQuantity, line.available, line.shortfall), (2, 3, True, 0))
        self.clients["free"].assert_called_once_with("eq1", START, END, "Bearer token")

    def test_a_raise_beyond_the_free_units_reports_the_shortfall(self):
        self.clients["free"].return_value = 1
        self.event(equipmentLines=[LINE])

        [line] = self.assess_new(equipmentLines=[{"equipmentId": "eq1", "quantity": 5}]).equipmentAvailability

        self.assertEqual((line.available, line.shortfall), (False, 2))

    def test_a_new_type_needs_its_whole_quantity(self):
        self.clients["free"].return_value = 4
        self.event(equipmentLines=[LINE])

        impact = self.assess_new(equipmentLines=[LINE, {"equipmentId": "eq3", "quantity": 6}])

        [line] = impact.equipmentAvailability
        self.assertEqual(
            (line.equipmentId, line.equipmentName, line.currentQuantity, line.heldQuantity, line.available, line.shortfall),
            ("eq3", "Speaker", 0, 0, False, 2),
        )
        # Only the projector reservation's type is unchanged, so it is not affected.
        self.assertEqual(impact.equipmentReservations, [])

    def test_a_lower_quantity_affects_its_reservation_but_needs_no_stock(self):
        self.event(equipmentLines=[LINE])

        impact = self.assess_new(equipmentLines=[{"equipmentId": "eq1", "quantity": 1}])

        self.assertIsNone(impact.equipmentAvailability)
        self.assertEqual([row.reservationId for row in impact.equipmentReservations], ["rsv-1"])
        self.clients["free"].assert_not_called()

    def test_moving_the_event_judges_the_raise_at_the_new_period(self):
        self.clients["free"].return_value = 4
        self.event(equipmentLines=[LINE])
        start, end = START + timedelta(days=7), END + timedelta(days=7)

        impact = self.assess_new(proposedStartAt=start, proposedEndAt=end, equipmentLines=[{"equipmentId": "eq1", "quantity": 5}])

        [line] = impact.equipmentAvailability
        # The current reservation is for the old date, so none of it is held at the new one.
        self.assertEqual((line.heldQuantity, line.available, line.shortfall), (0, False, 1))
        self.clients["free"].assert_called_once_with("eq1", start, end, "Bearer token")


class TestAccepting(ReviewCase):
    """AC6."""

    def test_accepting_applies_the_new_quantities_and_logs_them(self):
        self.event(equipmentLines=[LINE])
        raised = self.raise_(equipmentLines=[{"equipmentId": "eq1", "quantity": 5}])

        self.accept(raised.changeRequestId)

        self.assertEqual(self.stored().equipmentLines, [{"equipmentId": "eq1", "quantity": 5, "technicalNotes": ""}])
        logged = self.db.query(EventFieldChange).filter_by(field="equipmentLines").one()
        self.assertEqual((logged.oldValue, logged.newValue, logged.changedBy), ("2 x eq1", "5 x eq1", "coord-1"))

    def test_new_quantities_on_an_event_with_arrangements_need_confirming(self):
        self.mocks["affected"].return_value = [VENUE]
        self.event(equipmentLines=[LINE])
        raised = self.raise_(equipmentLines=[{"equipmentId": "eq1", "quantity": 5}])

        error = self.refused(self.accept, raised.changeRequestId)

        self.assertEqual((error.status_code, error.detail["significantFields"]), (409, ["equipmentLines"]))
        self.assertEqual(self.stored().equipmentLines, [LINE])

    def test_the_organiser_is_told_which_arrangements_will_be_re_checked(self):
        self.mocks["affected"].return_value = [VENUE]
        self.mocks["flag"].return_value = [VENUE]
        self.event()
        raised = self.raise_(expectedAttendance=200)

        accepted = self.accept(raised.changeRequestId, confirm=True)

        self.assertEqual(accepted.status, "accepted")
        self.assertEqual(self.stored().expectedAttendance, 200)
        to, subject, body = self.last_email()
        self.assertEqual((to, subject), ("amy@apex.com", "Your change request for Summit was accepted"))
        self.assertIn("These arrangements will be re-checked: Venue booking at Marina Hall A.", body)
        self.assertEqual(self.mocks["inbox"].call_args.args[4], body)

    def test_with_nothing_flagged_nothing_is_listed(self):
        self.event()
        raised = self.raise_(description="New copy")

        self.accept(raised.changeRequestId)

        self.assertNotIn("re-checked", self.last_email()[2])


class TestDeclining(ReviewCase):
    """AC7."""

    def test_declining_needs_a_reason_and_leaves_the_event_as_it_was(self):
        self.event()
        raised = self.raise_(eventName="Should not apply")
        with self.assertRaises(ValidationError):
            ChangeRequestDecline(reason="")

        declined = self.decline(raised.changeRequestId, "Venue cannot move that week")

        self.assertEqual((declined.status, declined.decisionReason), ("declined", "Venue cannot move that week"))
        self.assertEqual(self.stored().eventName, "Summit")
        self.assertEqual(self.db.query(EventFieldChange).count(), 0)
        self.assertIn("Reason: Venue cannot move that week", self.last_email()[2])
        self.assertFalse(declined.narrowerRequested)


class TestNarrowerRequest(ReviewCase):
    """AC8."""

    def test_part_of_a_request_is_accepted_by_declining_it_and_asking_for_a_narrower_one(self):
        self.event()
        raised = self.raise_(eventName="New name", expectedAttendance=200)

        declined = self.decline_narrower(raised.changeRequestId, "Please raise attendance only; the name stays.")

        self.assertEqual((declined.status, declined.narrowerRequested), ("declined", True))
        stored = self.stored()
        self.assertEqual((stored.eventName, stored.expectedAttendance), ("Summit", 50))
        self.assertEqual(self.db.query(EventFieldChange).count(), 0)
        self.mocks["flag"].assert_not_called()
        body = self.last_email()[2]
        self.assertIn("Reason: Please raise attendance only; the name stays.", body)
        self.assertIn("please raise a new request with only that part", body)
        self.assertTrue(self.service.list_change_requests("e1", ORGANISER)[0].narrowerRequested)

    def test_the_organiser_can_then_raise_the_narrower_request(self):
        self.event()
        self.decline_narrower(self.raise_(eventName="New name", expectedAttendance=200).changeRequestId)

        narrower = self.raise_(expectedAttendance=200)

        self.assertEqual((narrower.status, narrower.proposedChanges), ("pending", {"expectedAttendance": 200}))


class TestActivityLog(ReviewCase):
    """AC9."""

    def test_an_accepted_request_logs_the_decision_fields_values_decider_and_time(self):
        self.event(purpose="Old purpose")
        raised = self.raise_(purpose="Logged purpose", expectedAttendance=80)

        accepted = self.accept(raised.changeRequestId, reason="Fine by the venue")

        [decision] = [entry for entry in self.log() if entry.kind == "change_request"]
        self.assertEqual((decision.decision, decision.changedBy, decision.note), ("accepted", "coord-1", "Fine by the venue"))
        self.assertEqual(decision.createdAt, accepted.reviewedAt)
        self.assertEqual(
            [(row.field, row.oldValue, row.newValue) for row in decision.changes],
            [("purpose", "Old purpose", "Logged purpose"), ("expectedAttendance", "50", "80")],
        )
        edits = {entry.field for entry in self.log() if entry.kind == "edit"}
        self.assertEqual(edits, {"purpose", "expectedAttendance"})

    def test_a_declined_request_is_logged_and_nothing_is_edited(self):
        self.event()
        raised = self.raise_(eventName="New name")

        self.decline_narrower(raised.changeRequestId, "Name stays")

        entries = self.log()
        self.assertEqual([entry.kind for entry in entries], ["change_request"])
        [decision] = entries
        self.assertEqual((decision.decision, decision.changedBy), ("declined", "coord-1"))
        self.assertEqual(decision.note, "Name stays A narrower request was asked for.")
        self.assertEqual([(row.field, row.oldValue, row.newValue) for row in decision.changes], [("eventName", "Summit", "New name")])

    def test_pending_and_withdrawn_requests_are_not_decisions(self):
        self.event()
        self.withdraw(self.raise_(description="A").changeRequestId)
        self.raise_(description="B")

        self.assertEqual([entry for entry in self.log() if entry.kind == "change_request"], [])


class TestReviewRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_service.organisation_names", return_value={}),
            patch("app.services.event_service.list_users", return_value=DIRECTORY),
            patch("app.services.event_service.send_notification", return_value=True),
            patch("app.services.event_service.record_notification", return_value=True),
            patch("app.services.event_service.publish_notification", return_value=True),
            patch("app.services.event_service.affected_arrangements", return_value=[]),
            patch("app.services.event_service.confirmed_bookings", return_value=[BOOKING]),
            patch("app.services.event_service.venue_details", return_value=MARINA),
            patch("app.services.event_service.registered_attendees", return_value=[ATTENDEE_ROW]),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch("app.routers.event.resolve_caller", return_value=ORGANISER)
        self.caller_mock = self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        insert_event(
            self.db, eventId="e1", status="planning", coordinatorId="coord-1", expectedAttendance=50, layoutPreference="Theatre"
        )

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def raise_(self, changes):
        self.caller_mock.return_value = ORGANISER
        response = self.client.post("/events/e1/change-requests", headers=HEADERS, json={"reason": "Bigger", "proposedChanges": changes})
        self.assertEqual(response.status_code, 201, response.text)
        self.caller_mock.return_value = COORDINATOR
        return response.json()["changeRequestId"]

    def test_impact_decline_with_a_narrower_ask_and_the_activity_log(self):
        raised = self.raise_({"expectedAttendance": 500})

        impact = self.client.get(f"/events/e1/change-requests/{raised}/impact", headers=HEADERS)

        self.assertEqual(impact.status_code, 200)
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})
        [capacity] = impact.json()["capacity"]
        self.assertEqual((capacity["capacity"], capacity["expectedAttendance"], capacity["overCapacity"]), (200, 500, True))
        self.assertIsNone(impact.json()["venueSuitability"])

        missing = self.client.post(f"/events/e1/change-requests/{raised}/decline", headers=HEADERS, json={})
        self.assertEqual(missing.status_code, 422)
        declined = self.client.post(
            f"/events/e1/change-requests/{raised}/decline",
            headers=HEADERS,
            json={"reason": "Raise it to 200 instead", "askNarrower": True},
        )
        self.assertEqual((declined.status_code, declined.json()["narrowerRequested"]), (200, True))
        self.assertEqual(self.client.get(f"/events/e1/change-requests/{raised}/impact", headers=HEADERS).status_code, 409)

        log = self.client.get("/events/e1/activity-log", headers=HEADERS).json()
        [decision] = [entry for entry in log if entry["kind"] == "change_request"]
        self.assertEqual(decision["decision"], "declined")
        self.assertEqual(decision["changes"], [{"field": "expectedAttendance", "oldValue": "50", "newValue": "500"}])

