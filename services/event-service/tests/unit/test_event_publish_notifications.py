import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from app.orchestration import clients
from app.services.audiences import people
from shared.exceptions.http import service_unavailable
from tests.unit.test_event_arrangement_clients import reply
from tests.unit.test_event_safety_reviews import DIRECTORY, SafetyCase

STAFF = DIRECTORY + [
    {"userId": "venue-1", "userName": "Carol", "email": "carol@connectsphere.com", "role": "venue"},
    {"userId": "tech-1", "userName": "Dev", "email": "dev@connectsphere.com", "role": "techsupport"},
]


class TestPeople(unittest.TestCase):
    EVENT = SimpleNamespace(organiserId="org-1", coordinatorId="coord-1")
    DIRECTORY = {user["userId"]: user for user in STAFF}

    def test_the_organiser_and_coordinator_come_from_the_event(self):
        self.assertEqual(
            people(self.EVENT, ["organiser", "coordinator"], {}),
            [{"userId": "org-1", "role": "organiser"}, {"userId": "coord-1", "role": "coordinator"}],
        )

    def test_a_role_audience_is_everyone_in_the_directory_with_that_role(self):
        self.assertEqual(
            people(self.EVENT, ["safety"], self.DIRECTORY),
            [{"userId": "safety-1", "role": "safety"}, {"userId": "safety-2", "role": "safety"}],
        )

    def test_an_unassigned_coordinator_is_left_out(self):
        self.assertEqual(people(SimpleNamespace(organiserId="org-1", coordinatorId=None), ["coordinator"], {}), [])

    def test_a_role_nobody_holds_is_empty(self):
        self.assertEqual(people(self.EVENT, ["venue"], {}), [])


class TestPublishClient(unittest.TestCase):
    def post_answering(self, response):
        client = MagicMock()
        client.__enter__.return_value.post.return_value = response
        return patch("app.orchestration.clients.httpx.Client", MagicMock(return_value=client)), client

    def publish(self, recipients=None):
        return clients.publish_notification(
            "booking.assigned",
            "e1",
            "e1:booking.assigned:a1",
            [{"userId": "coord-1", "role": "coordinator"}] if recipients is None else recipients,
            {"eventName": "Summit"},
            actor_id="u-lead",
            resource={"type": "event", "id": "e1"},
        )

    def test_a_published_trigger_is_posted_with_the_service_key(self):
        stub, client = self.post_answering(reply(201))
        with stub, patch.object(clients.settings, "internal_service_key", "secret"):
            self.assertTrue(self.publish())

        call = client.__enter__.return_value.post.call_args
        self.assertTrue(call.args[0].endswith("/notifications/publish"))
        self.assertEqual(
            call.kwargs["json"],
            {
                "trigger": "booking.assigned",
                "occurrenceId": "e1:booking.assigned:a1",
                "eventId": "e1",
                "actorId": "u-lead",
                "recipients": [{"userId": "coord-1", "role": "coordinator"}],
                "context": {"eventName": "Summit"},
                "resource": {"type": "event", "id": "e1"},
            },
        )
        self.assertEqual(call.kwargs["headers"], {"X-Service-Key": "secret"})

    def test_nothing_is_sent_when_there_is_nobody_to_tell(self):
        with patch("app.orchestration.clients.httpx.Client") as client:
            self.assertTrue(self.publish(recipients=[]))

        client.assert_not_called()

    def test_a_refused_or_unreachable_publish_is_false(self):
        stub, _client = self.post_answering(reply(403))
        with stub:
            self.assertFalse(self.publish())
        with patch("app.orchestration.clients.httpx.Client", side_effect=httpx.ConnectError("down")):
            self.assertFalse(self.publish())


class TestSafetyTriggers(SafetyCase):
    """SPM-93: the Safety Officer is told details were submitted, and the coordinator, organiser,
    venue staff and technical staff are told the decision."""

    def setUp(self):
        super().setUp()
        self.mocks["users"].return_value = STAFF
        self.event()

    def last(self):
        call = self.published.call_args
        trigger, event_id, occurrence, recipients, context = call.args
        return trigger, event_id, occurrence, [r["userId"] for r in recipients], context, call.kwargs

    def test_every_officer_is_told_the_details_were_submitted(self):
        review = self.submit()

        trigger, event_id, occurrence, to, context, extra = self.last()
        self.assertEqual((trigger, event_id), ("safety.submitted", "e1"))
        self.assertEqual(occurrence, f"e1:safety.submitted:{review.reviewId}")
        self.assertEqual(to, ["safety-1", "safety-2"])
        self.assertEqual(context, {"eventName": "Summit"})
        self.assertEqual(extra["actor_id"], "coord-1")
        self.assertEqual(extra["resource"], {"type": "safety_review", "id": review.reviewId})

    def test_an_approval_goes_to_the_coordinator_organiser_venue_and_technical_staff_with_the_note(self):
        review = self.submit()

        self.approve(review.reviewId, note="Good plan")

        trigger, _event_id, occurrence, to, context, extra = self.last()
        self.assertEqual(trigger, "safety.approved")
        self.assertEqual(occurrence, f"e1:safety.decided:{review.reviewId}")
        self.assertEqual(to, ["coord-1", "org-1", "venue-1", "tech-1"])
        self.assertEqual(context, {"eventName": "Summit", "note": "Good plan"})
        self.assertEqual(extra["actor_id"], "safety-1")

    def test_an_approval_without_a_note_sends_an_empty_one(self):
        review = self.submit()

        self.approve(review.reviewId)

        self.assertEqual(self.last()[4], {"eventName": "Summit", "note": ""})

    def test_a_rejection_carries_the_reason(self):
        review = self.submit()

        self.reject(review.reviewId)

        trigger, _event_id, _occurrence, to, context, _extra = self.last()
        self.assertEqual(trigger, "safety.rejected")
        self.assertEqual(to, ["coord-1", "org-1", "venue-1", "tech-1"])
        self.assertEqual(context, {"eventName": "Summit", "reason": "Exits blocked by the stage."})

    def test_requested_changes_say_which_arrangements_were_flagged(self):
        review = self.submit()

        self.request_changes(review.reviewId, affected=("venue",))

        trigger, _event_id, _occurrence, _to, context, _extra = self.last()
        self.assertEqual(trigger, "safety.changes_requested")
        self.assertEqual(
            context["reason"], "Move the stage away from exit B. Flagged for re-checking: venue arrangements."
        )

    def test_requested_changes_with_nothing_flagged_keep_the_reason_as_written(self):
        review = self.submit()

        self.request_changes(review.reviewId)

        self.assertEqual(self.last()[4]["reason"], "Move the stage away from exit B.")

    def test_an_unreachable_directory_still_tells_the_coordinator_and_organiser(self):
        review = self.submit()
        self.mocks["users"].side_effect = service_unavailable("down")

        self.reject(review.reviewId)

        self.assertEqual(self.last()[3], ["coord-1", "org-1"])
