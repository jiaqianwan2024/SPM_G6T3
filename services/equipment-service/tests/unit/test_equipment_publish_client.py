from unittest import TestCase
from unittest.mock import MagicMock, patch

import httpx

from app.core.config import settings
from app.orchestration import clients

EVENT = {"coordinatorId": "u-coord", "organiserId": "u-org"}


class TestEventRecipients(TestCase):
    def test_the_named_roles_are_returned_in_order(self):
        self.assertEqual(
            clients.event_recipients(EVENT, ("coordinator", "organiser")),
            [{"userId": "u-coord", "role": "coordinator"}, {"userId": "u-org", "role": "organiser"}],
        )

    def test_a_role_with_nobody_assigned_is_left_out(self):
        self.assertEqual(
            clients.event_recipients({"organiserId": "u-org"}, ("coordinator", "organiser")),
            [{"userId": "u-org", "role": "organiser"}],
        )


class TestPublishNotification(TestCase):
    def publish(self, response=None, error=None, recipients=None):
        client = MagicMock()
        client.__enter__.return_value = client
        if error:
            client.post.side_effect = error
        else:
            client.post.return_value = response
        with patch.object(clients.httpx, "Client", return_value=client):
            ok = clients.publish_notification(
                "equipment.released",
                "e1",
                "e1:equipment.released:r1",
                [{"userId": "u-coord", "role": "coordinator"}] if recipients is None else recipients,
                {"eventName": "Summit", "reason": "No longer needed"},
                actor_id="u-tech",
            )
        return ok, client

    def test_it_posts_the_occurrence_with_the_service_key(self):
        with patch.object(settings, "internal_service_key", "key-1"):
            ok, client = self.publish(MagicMock(status_code=201))

        self.assertTrue(ok)
        url = client.post.call_args.args[0]
        self.assertTrue(url.endswith("/notifications/publish"))
        body = client.post.call_args.kwargs["json"]
        self.assertEqual((body["trigger"], body["eventId"], body["actorId"]), ("equipment.released", "e1", "u-tech"))
        self.assertEqual(client.post.call_args.kwargs["headers"], {"X-Service-Key": "key-1"})

    def test_with_nobody_to_tell_nothing_is_sent(self):
        ok, client = self.publish(recipients=[])

        self.assertTrue(ok)
        client.post.assert_not_called()

    def test_an_unreachable_service_is_reported_not_raised(self):
        ok, _ = self.publish(error=httpx.ConnectError("down"))

        self.assertFalse(ok)

    def test_a_refusal_is_reported_not_raised(self):
        ok, _ = self.publish(MagicMock(status_code=422))

        self.assertFalse(ok)
