import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.event import EventDraftUpsert, EventIntake, OrganiserDraftPatch
from tests.unit.support import END, START, EventCase, draft_payload, event_create

OPENS = datetime(2026, 9, 1, 9, 0)
CLOSES = datetime(2026, 10, 1, 18, 0)


class TestRegistrationNeededAtIntake(unittest.TestCase):
    def intake(self, **overrides):
        data = dict(eventName="Summit", proposedStartAt=START, proposedEndAt=END, expectedAttendance=20)
        data.update(overrides)
        return EventIntake(**data)

    def test_a_request_with_dates_must_say_whether_registration_is_needed(self):
        with self.assertRaises(ValidationError) as ctx:
            self.intake()

        self.assertIn("registrationEnabled", str(ctx.exception))

    def test_either_answer_is_accepted(self):
        self.assertFalse(self.intake(registrationEnabled=False).registrationEnabled)
        self.assertTrue(self.intake(registrationEnabled=True).registrationEnabled)

    def test_a_name_only_draft_need_not_answer(self):
        draft = EventIntake(eventName="Idea").to_draft()

        self.assertIsNone(draft.registrationEnabled)

    def test_the_answer_period_and_capacity_carry_into_the_draft_and_the_request(self):
        intake = self.intake(
            registrationEnabled=True, registrationOpensAt=OPENS, registrationClosesAt=CLOSES, capacity=50
        )

        for built in (intake.to_draft(), intake.to_create()):
            self.assertEqual(
                (built.registrationEnabled, built.registrationOpensAt, built.registrationClosesAt, built.capacity),
                (True, OPENS, CLOSES, 50),
            )

    def test_a_close_that_is_not_after_the_open_is_rejected(self):
        for build in (
            lambda: event_create(registrationOpensAt=OPENS, registrationClosesAt=OPENS),
            lambda: draft_payload(registrationOpensAt=OPENS, registrationClosesAt=OPENS),
        ):
            with self.assertRaises(ValidationError) as ctx:
                build()
            self.assertIn("after registrationOpensAt", str(ctx.exception))

    def test_a_close_later_than_the_event_start_is_rejected(self):
        late = START.replace(hour=10)

        with self.assertRaises(ValidationError) as ctx:
            event_create(registrationOpensAt=OPENS, registrationClosesAt=late)
        self.assertIn("no later than the event start", str(ctx.exception))
        with self.assertRaises(ValidationError):
            draft_payload(proposedStartAt=START, registrationOpensAt=OPENS, registrationClosesAt=late)

    def test_a_close_exactly_at_the_start_is_allowed(self):
        self.assertEqual(event_create(registrationOpensAt=OPENS, registrationClosesAt=START).registrationClosesAt, START)

    def test_offset_aware_times_are_compared_in_utc(self):
        opens = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)

        with self.assertRaises(ValidationError):
            event_create(registrationOpensAt=opens, registrationClosesAt=OPENS)

    def test_a_draft_patch_normalises_registration_times_to_naive_utc(self):
        patch = OrganiserDraftPatch(registrationOpensAt=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc))

        self.assertEqual(patch.registrationOpensAt, OPENS)


class TestRegistrationOnDrafts(EventCase):
    def test_a_draft_keeps_the_organisers_registration_answer_period_and_capacity(self):
        created = self.service.create_draft(
            draft_payload(registrationEnabled=True, registrationOpensAt=OPENS, registrationClosesAt=CLOSES, capacity=60),
            "org-1",
            "o1",
        )

        self.assertEqual(
            (created.registrationEnabled, created.registrationOpensAt, created.registrationClosesAt, created.capacity),
            (True, OPENS, CLOSES, 60),
        )

    def test_an_unanswered_draft_stays_not_needed(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        self.assertFalse(created.registrationEnabled)
        self.assertFalse(created.registrationDetailsOutstanding)

    def test_saving_a_draft_again_changes_only_what_was_sent(self):
        created = self.service.create_draft(
            draft_payload(registrationEnabled=True, registrationOpensAt=OPENS, capacity=60), "org-1", "o1"
        )

        renamed = self.service.update_draft(created.eventId, draft_payload(eventName="Renamed"), "org-1")
        changed = self.service.update_draft(
            created.eventId, draft_payload(registrationEnabled=False, capacity=10), "org-1"
        )

        self.assertEqual((renamed.registrationEnabled, renamed.registrationOpensAt, renamed.capacity), (True, OPENS, 60))
        self.assertEqual((changed.registrationEnabled, changed.capacity), (False, 10))

    def test_patching_a_draft_saves_registration_settings(self):
        created = self.service.create_draft(draft_payload(proposedStartAt=START, proposedEndAt=END), "org-1", "o1")

        saved = self.service.patch_own_draft(
            created.eventId,
            OrganiserDraftPatch(
                registrationEnabled=True, registrationOpensAt=OPENS, registrationClosesAt=CLOSES, capacity=40
            ),
            "org-1",
        )

        self.assertEqual((saved.registrationEnabled, saved.registrationClosesAt, saved.capacity), (True, CLOSES, 40))

    def test_patching_a_close_that_breaks_the_rules_is_refused_and_nothing_is_saved(self):
        created = self.service.create_draft(
            draft_payload(proposedStartAt=START, proposedEndAt=END, registrationEnabled=True, registrationOpensAt=OPENS),
            "org-1",
            "o1",
        )

        for closes, message in ((OPENS, "after registrationOpensAt"), (START.replace(hour=10), "event start")):
            with self.assertRaises(HTTPException) as ctx:
                self.service.patch_own_draft(created.eventId, OrganiserDraftPatch(registrationClosesAt=closes), "org-1")
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertIn(message, ctx.exception.detail)

        self.assertIsNone(self.service.get_event(created.eventId).registrationClosesAt)


class TestRegistrationDetailsOutstanding(EventCase):
    def submit(self, **overrides):
        return self.service.create_event(event_create(**overrides), "org-1", "o1")

    def test_registration_needed_with_a_blank_period_still_submits_and_is_flagged(self):
        submitted = self.submit(registrationOpensAt=None, registrationClosesAt=None)

        self.assertEqual(submitted.status, "submitted")
        self.assertTrue(submitted.registrationDetailsOutstanding)

    def test_a_blank_capacity_or_a_single_blank_time_is_flagged(self):
        self.assertTrue(self.submit(capacity=0).registrationDetailsOutstanding)
        self.assertTrue(self.submit(registrationOpensAt=None).registrationDetailsOutstanding)
        self.assertTrue(self.submit(registrationClosesAt=None).registrationDetailsOutstanding)

    def test_complete_details_are_not_flagged(self):
        self.assertFalse(self.submit().registrationDetailsOutstanding)

    def test_registration_not_needed_is_never_flagged(self):
        submitted = self.submit(registrationEnabled=False, registrationOpensAt=None, capacity=0)

        self.assertFalse(submitted.registrationDetailsOutstanding)

    def test_the_flag_reaches_the_coordinator_on_the_submission_queue(self):
        self.submit(eventName="Needs details", registrationOpensAt=None)

        queued = self.service.list_submission_queue()

        self.assertTrue(queued[0].registrationDetailsOutstanding)
