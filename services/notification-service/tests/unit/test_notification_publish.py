from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.notification import Notification
from app.services import notifier
from app.services.notifier import PublishError
from app.services.triggers import TRIGGERS
from shared.auth.service_key import service_key_headers
from shared.testing.cases import ServiceTestCase

COORD = {"userId": "u-coord", "role": "coordinator"}
LEAD = {"userId": "u-lead", "role": "coordinator"}
OTHER = {"userId": "u-other", "role": "coordinator"}
ATTENDEE = {"userId": "u-att", "role": "attendee"}
CONTEXT = {"eventName": "AI in Events Summit"}


class TestPublish(ServiceTestCase):
    def publish(self, trigger="booking.assigned", recipients=None, context=None, occurrence="occ-1", **kwargs):
        result = notifier.publish(
            self.db,
            trigger,
            "e1",
            occurrence,
            [COORD] if recipients is None else recipients,
            CONTEXT if context is None else context,
            **kwargs,
        )
        self.db.commit()
        return result

    def rows(self):
        return self.db.query(Notification).all()

    def test_one_notification_is_stored_per_recipient_with_the_registry_message(self):
        result = self.publish(resource_type="booking", resource_id="a7")

        self.assertEqual((result.created, result.skipped_actor, result.skipped_attendee, result.skipped_duplicate), (1, 0, 0, 0))
        row = self.rows()[0]
        self.assertEqual(row.userId, "u-coord")
        self.assertEqual(row.eventId, "e1")
        self.assertEqual(row.type, "booking.assigned")
        self.assertEqual(row.title, "New booking request assigned")
        self.assertIn("AI in Events Summit", row.body)
        self.assertEqual(row.link, "/app/events/e1")
        self.assertEqual((row.resourceType, row.resourceId), ("booking", "a7"))
        self.assertEqual(row.occurrenceId, "occ-1")
        self.assertFalse(row.isRead)

    def test_every_registered_trigger_names_the_event(self):
        context = {"eventName": "AI in Events Summit", "reason": "Exit blocked."}
        for key, trigger in TRIGGERS.items():
            with self.subTest(trigger=key):
                _, body, link = notifier.render(trigger, "e9", context)
                self.assertIn("AI in Events Summit", body)
                self.assertEqual(link, "/app/events/e9")

    def test_the_person_who_did_the_action_is_not_notified(self):
        result = self.publish(recipients=[COORD, {"userId": "u-lead", "role": "coordinator"}], actor_id="u-lead")

        self.assertEqual((result.created, result.skipped_actor), (1, 1))
        self.assertEqual([row.userId for row in self.rows()], ["u-coord"])

    def test_an_attendee_is_skipped_when_the_trigger_is_not_attendee_visible(self):
        result = self.publish(recipients=[ATTENDEE, COORD])

        self.assertEqual((result.created, result.skipped_attendee), (1, 1))
        self.assertEqual([row.userId for row in self.rows()], ["u-coord"])

    def test_an_attendee_is_notified_when_the_trigger_is_attendee_visible(self):
        visible = replace(
            TRIGGERS["booking.assigned"],
            key="event.cancelled",
            recipient_roles=frozenset({"attendee"}),
            attendee_visible=True,
        )
        with patch.dict(TRIGGERS, {"event.cancelled": visible}):
            result = self.publish(trigger="event.cancelled", recipients=[ATTENDEE])

        self.assertEqual((result.created, result.skipped_attendee), (1, 0))

    def test_a_role_the_trigger_is_not_for_is_refused(self):
        with self.assertRaisesRegex(PublishError, "venue cannot receive booking.assigned"):
            self.publish(recipients=[{"userId": "u-venue", "role": "venue"}])
        self.assertEqual(self.rows(), [])

    def test_an_unknown_trigger_is_refused(self):
        with self.assertRaisesRegex(PublishError, "Unknown trigger: nope"):
            self.publish(trigger="nope")

    def test_a_trigger_missing_its_context_is_refused(self):
        with self.assertRaisesRegex(PublishError, "safety.rejected needs: reason"):
            self.publish(trigger="safety.rejected", context=CONTEXT)

    def test_an_optional_note_is_included_when_sent_and_leaves_no_gap_when_not(self):
        self.publish(trigger="safety.approved", context={**CONTEXT, "note": "Keep the aisles clear."}, occurrence="a")
        self.publish(trigger="safety.approved", context=CONTEXT, occurrence="b")

        bodies = {row.occurrenceId: row.body for row in self.rows()}
        self.assertTrue(bodies["a"].endswith("Keep the aisles clear."))
        self.assertTrue(bodies["b"].endswith("AI in Events Summit."))

    def test_a_released_reservation_tells_the_coordinator_and_organiser_with_the_reason(self):
        ctx = {**CONTEXT, "reason": "Stock moved to another venue"}
        result = self.publish(
            trigger="equipment.released",
            recipients=[COORD, {"userId": "u-org", "role": "organiser"}],
            context=ctx,
            actor_id="u-tech",
        )

        self.assertEqual(result.created, 2)
        self.assertEqual({row.userId for row in self.rows()}, {"u-coord", "u-org"})
        for row in self.rows():
            self.assertEqual(row.title, "Equipment released")
            self.assertEqual(
                row.body,
                "Equipment for AI in Events Summit was released. Reason: Stock moved to another venue",
            )

    def test_a_release_with_no_reason_is_refused_and_notifies_no_one(self):
        for context in (CONTEXT, {**CONTEXT, "reason": "   "}):
            with self.subTest(context=context):
                with self.assertRaisesRegex(PublishError, "equipment.released needs: reason"):
                    self.publish(trigger="equipment.released", context=context)
        self.assertEqual(self.rows(), [])

    def test_a_release_notice_is_not_for_technical_support(self):
        with self.assertRaises(PublishError):
            self.publish(
                trigger="equipment.released",
                recipients=[{"userId": "u-tech", "role": "techsupport"}],
                context={**CONTEXT, "reason": "No longer needed"},
            )

    SHORTFALL = {
        "eventName": "AI in Events Summit",
        "equipmentName": "Projector",
        "shortfall": "2 of 5 short",
        "reason": "Two units are out for repair",
    }

    def test_a_shortfall_names_the_line_the_shortfall_the_reason_and_the_alternative(self):
        self.publish(
            trigger="equipment.shortfall",
            context={**self.SHORTFALL, "alternative": "Short-throw projector"},
        )

        row = self.rows()[0]
        self.assertEqual(row.userId, "u-coord")
        self.assertEqual(row.title, "Equipment cannot be fully supplied")
        self.assertEqual(
            row.body,
            "Projector for AI in Events Summit cannot be fully supplied. Shortfall: 2 of 5 short. "
            "Reason: Two units are out for repair. Suggested alternative: Short-throw projector",
        )

    def test_an_alternative_follows_a_reason_that_already_ends_in_a_full_stop(self):
        self.publish(
            trigger="equipment.shortfall",
            context={**self.SHORTFALL, "reason": "Out for repair.", "alternative": "Short-throw projector"},
        )

        self.assertTrue(self.rows()[0].body.endswith("Reason: Out for repair. Suggested alternative: Short-throw projector"))

    def test_a_shortfall_without_an_alternative_leaves_no_gap(self):
        self.publish(trigger="equipment.shortfall", context=self.SHORTFALL)

        self.assertTrue(self.rows()[0].body.endswith("Reason: Two units are out for repair"))

    def test_a_shortfall_needs_every_fact_and_goes_only_to_the_coordinator(self):
        with self.assertRaisesRegex(PublishError, "equipment.shortfall needs: shortfall, reason"):
            self.publish(
                trigger="equipment.shortfall",
                context={"eventName": "AI in Events Summit", "equipmentName": "Projector"},
            )
        with self.assertRaises(PublishError):
            self.publish(
                trigger="equipment.shortfall",
                recipients=[{"userId": "u-org", "role": "organiser"}],
                context=self.SHORTFALL,
            )
        self.assertEqual(self.rows(), [])

    def test_a_clarification_reply_names_the_event_the_answer_and_a_late_review(self):
        self.publish(
            trigger="clarification.replied",
            context={
                "eventName": "AI in Events Summit",
                "eventId": "e1",
                "message": "Attendance stays at 80.",
                "reviewStatus": "planning",
            },
        )

        row = self.rows()[0]
        self.assertEqual(row.title, "New reply on AI in Events Summit")
        self.assertEqual(
            row.body,
            "AI in Events Summit (e1) has a new clarification reply: Attendance stays at 80. "
            "This request is no longer awaiting review; it is now planning.",
        )
        self.assertEqual(row.link, "/app/events/e1")

    def test_a_clarification_reply_while_still_in_review_does_not_add_the_late_sentence(self):
        self.publish(
            trigger="clarification.replied",
            context={"eventName": "AI in Events Summit", "eventId": "e1", "message": "Attendance stays at 80."},
        )

        self.assertEqual(
            self.rows()[0].body,
            "AI in Events Summit (e1) has a new clarification reply: Attendance stays at 80.",
        )

    def test_a_recipient_listed_twice_is_notified_once(self):
        result = self.publish(recipients=[COORD, COORD])

        self.assertEqual((result.created, result.skipped_duplicate), (1, 1))
        self.assertEqual(len(self.rows()), 1)

    def test_repeating_an_occurrence_does_not_notify_anyone_twice(self):
        self.publish(recipients=[COORD])
        again = self.publish(recipients=[COORD, {"userId": "u-new", "role": "coordinator"}])

        self.assertEqual((again.created, again.skipped_duplicate), (1, 1))
        self.assertEqual(sorted(row.userId for row in self.rows()), ["u-coord", "u-new"])

    def test_a_new_occurrence_notifies_the_same_person_again(self):
        self.publish(occurrence="assignment-1")
        again = self.publish(occurrence="assignment-2")

        self.assertEqual(again.created, 1)
        self.assertEqual(len(self.rows()), 2)

    def test_no_recipients_stores_nothing(self):
        result = self.publish(recipients=[])

        self.assertEqual(tuple(result), (0, 0, 0, 0))
        self.assertEqual(self.rows(), [])


class TestPublishRoute(ServiceTestCase):
    KEY = "test-service-key"

    def setUp(self):
        super().setUp()
        # No user-token override: this route must work with the service key alone.
        self.key = patch.object(settings, "internal_service_key", self.KEY)
        self.key.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.key.stop()
        super().tearDown()

    def body(self, **overrides):
        body = {
            "trigger": "booking.assigned",
            "occurrenceId": "e1:booking.assigned:a1",
            "eventId": "e1",
            "recipients": [COORD],
            "context": CONTEXT,
        }
        body.update(overrides)
        return body

    def post(self, body=None, key=KEY):
        headers = {"X-Service-Key": key} if key is not None else {}
        return self.client.post("/notifications/publish", json=body or self.body(), headers=headers)

    def test_a_service_publishes_without_a_user_token(self):
        response = self.post(self.body(actorId="u-lead", recipients=[LEAD, COORD]))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"created": 1, "skipped": {"actor": 1, "attendeeHidden": 0, "duplicate": 0}})
        row = self.db.query(Notification).one()
        self.assertEqual(row.userId, "u-coord")

    def test_the_skip_counts_are_reported(self):
        response = self.post(self.body(actorId="u-lead", recipients=[LEAD, ATTENDEE, OTHER, OTHER]))

        self.assertEqual(response.json(), {"created": 1, "skipped": {"actor": 1, "attendeeHidden": 1, "duplicate": 1}})

    def test_a_resource_is_stored_with_the_notification(self):
        self.post(self.body(resource={"type": "booking", "id": "a7"}))

        row = self.db.query(Notification).one()
        self.assertEqual((row.resourceType, row.resourceId), ("booking", "a7"))

    def test_a_missing_key_is_refused(self):
        self.assertEqual(self.post(key=None).status_code, 403)
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_a_wrong_key_is_refused(self):
        self.assertEqual(self.post(key="not-the-key").status_code, 403)
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_a_service_with_no_key_configured_refuses_everyone(self):
        with patch.object(settings, "internal_service_key", ""):
            self.assertEqual(self.post(key="").status_code, 403)
            self.assertEqual(self.post(key=self.KEY).status_code, 403)

    def test_an_unknown_trigger_is_unprocessable(self):
        response = self.post(self.body(trigger="nope"))

        self.assertEqual(response.status_code, 422)
        self.assertIn("Unknown trigger", response.json()["detail"])

    def test_a_recipient_with_the_wrong_role_is_unprocessable_and_nothing_is_saved(self):
        response = self.post(self.body(recipients=[COORD, {"userId": "u-venue", "role": "venue"}]))

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_the_user_token_routes_still_need_a_token(self):
        self.assertEqual(self.client.get("/notifications/unread-count").status_code, 401)


class TestServiceKeyHeaders(ServiceTestCase):
    def test_the_key_is_sent_when_configured_and_omitted_when_not(self):
        self.assertEqual(service_key_headers("secret"), {"X-Service-Key": "secret"})
        self.assertEqual(service_key_headers(""), {})
