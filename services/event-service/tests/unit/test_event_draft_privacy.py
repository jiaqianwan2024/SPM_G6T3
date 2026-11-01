from fastapi import HTTPException

from tests.unit.support import EventCase, insert_event

ORGANISER = {"userId": "org-1", "role": "organiser", "organisationId": "o1"}
COLLEAGUE = {"userId": "org-2", "role": "organiser", "organisationId": "o1"}
STAFF = [
    {"userId": "coord-1", "role": "coordinator"},
    {"userId": "lead-1", "role": "coordinatorlead"},
    {"userId": "venue-1", "role": "venue"},
    {"userId": "tech-1", "role": "techsupport"},
    {"userId": "safety-1", "role": "safety"},
]


class TestDraftsStayWithTheOrganisation(EventCase):
    """SPM-79 AC6: no internal ConnectSphere user can see a draft before it is submitted."""

    def test_staff_cannot_read_a_draft_or_its_activity_log(self):
        for status in ("draft", "discarded"):
            insert_event(self.db, eventId=f"e-{status}", status=status)
            for caller in STAFF:
                for read in (self.service.get_event, self.service.get_activity_log):
                    with self.subTest(status=status, role=caller["role"], read=read.__name__):
                        with self.assertRaises(HTTPException) as ctx:
                            read(f"e-{status}", None, caller)
                        self.assertEqual(ctx.exception.status_code, 404)

    def test_the_organisation_still_reads_its_own_draft(self):
        insert_event(self.db, eventId="e-draft", status="draft")

        for caller in (ORGANISER, COLLEAGUE):
            self.assertEqual(self.service.get_event("e-draft", None, caller).status, "draft")
            self.assertEqual(self.service.get_activity_log("e-draft", None, caller), [])

    def test_staff_read_a_request_once_it_is_submitted(self):
        insert_event(self.db, eventId="e-sent", status="submitted")

        for caller in STAFF:
            self.assertEqual(self.service.get_event("e-sent", None, caller).status, "submitted")
