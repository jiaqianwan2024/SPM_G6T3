from unittest.mock import patch

from tests.unit.support import EventCase, draft_payload, event_create


class TestSubmissionNotice(EventCase):
    def sent(self):
        return [call for call in self.published.call_args_list if call.args[0] == "booking.submitted"]

    def test_a_new_request_tells_the_coordinator_lead(self):
        event = self.service.create_event(event_create(eventName="Summit"), "org-1", "o1")

        call = self.sent()[0]
        self.assertEqual(call.args[1], event.eventId)
        self.assertEqual(call.args[3], [{"userId": "lead-1", "role": "coordinatorlead"}])
        self.assertEqual(call.args[4], {"eventName": "Summit"})
        self.assertEqual(call.kwargs["actor_id"], "org-1")
        self.assertEqual(call.kwargs["resource"], {"type": "event", "id": event.eventId})
        self.assertTrue(call.args[2].startswith(f"{event.eventId}:booking.submitted:"))

    def test_submitting_a_draft_tells_the_lead_but_saving_one_does_not(self):
        draft = self.service.create_draft(draft_payload(), "org-1", "o1")
        self.assertEqual(self.sent(), [])

        self.service.submit_draft(draft.eventId, event_create(eventName="From draft"), "org-1")

        call = self.sent()[0]
        self.assertEqual(call.args[1], draft.eventId)
        self.assertEqual(call.args[4], {"eventName": "From draft"})

    def test_every_lead_is_told(self):
        directory = {
            "lead-1": {"userId": "lead-1", "role": "coordinatorlead"},
            "lead-2": {"userId": "lead-2", "role": "coordinatorlead"},
        }
        with patch("app.services.event_service.users_with_roles", return_value=directory):
            self.service.create_event(event_create(), "org-1", "o1")

        self.assertEqual([row["userId"] for row in self.sent()[0].args[3]], ["lead-1", "lead-2"])

    def test_an_unreadable_user_directory_does_not_stop_the_submission(self):
        with patch("app.services.event_service.users_with_roles", return_value=None):
            event = self.service.create_event(event_create(), "org-1", "o1")

        self.assertEqual(event.status, "submitted")
        self.assertEqual(self.sent()[0].args[3], [])
