import unittest

from app.schemas.event import (
    ChangeRequestCreate,
    EventCreate,
    EventDraftUpsert,
    EventIntake,
    EventUpdate,
    OrganiserDraftPatch,
)

DETAILS = {
    "eventName": "AUTO-category",
    "purpose": "Share",
    "proposedStartAt": "2026-11-01T09:00:00",
    "proposedEndAt": "2026-11-01T17:00:00",
    "expectedAttendance": 10,
}


class TestCategorySpelling(unittest.TestCase):
    """A known category is stored in its listed spelling whatever case it arrives in,
    so the category filters never show "meeting" and "Meeting" as two options."""

    def test_a_submitted_event_stores_the_listed_spelling(self):
        self.assertEqual(EventCreate(**DETAILS, category="meeting").category, "Meeting")

    def test_every_way_of_saving_an_event_stores_the_listed_spelling(self):
        saved = [
            EventIntake(eventName="AUTO-category", category="WORKSHOP"),
            EventDraftUpsert(eventName="AUTO-category", category=" networking "),
            OrganiserDraftPatch(category="conference"),
            EventUpdate(category="mEeTiNg"),
        ]

        self.assertEqual(
            [schema.category for schema in saved], ["Workshop", "Networking", "Conference", "Meeting"]
        )

    def test_a_change_request_proposes_the_listed_spelling(self):
        request = ChangeRequestCreate(reason="Smaller group", proposedChanges={"category": "workshop"})

        self.assertEqual(request.proposedChanges, {"category": "Workshop"})

    def test_a_category_that_is_not_listed_is_kept_as_typed(self):
        self.assertEqual(EventUpdate(category=" Gala dinner ").category, "Gala dinner")

    def test_a_category_can_still_be_left_out_of_a_draft(self):
        self.assertIsNone(EventDraftUpsert(eventName="AUTO-category").category)


if __name__ == "__main__":
    unittest.main()
