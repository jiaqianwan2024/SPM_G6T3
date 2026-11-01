"""Technical support are told when a coordinator asks for equipment or changes a request."""

from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.models.equipment_request import EquipmentRequest
from app.orchestration.clients import technical_support_recipients
from app.schemas.equipment import EquipmentRequestCreate
from shared.auth.deps import require_authenticated_user
from tests.unit.support import COORDINATOR, END, START, EquipmentCase, equipment_create

TOKEN = "Bearer token"
TECHS = [{"userId": "u4", "role": "techsupport"}, {"userId": "u12", "role": "techsupport"}]


class NoticeCase(EquipmentCase):
    def setUp(self):
        super().setUp()
        self.projector = self.service.create_equipment(
            equipment_create(code="PX", name="Projector"), {"userId": "u-tech", "role": "techsupport"}
        ).equipmentId
        self.patches = {
            "event": patch("app.services.equipment_service._event_record", return_value={"eventName": "AI Summit"}),
            "techs": patch("app.services.equipment_service.technical_support_recipients", return_value=TECHS),
            "publish": patch("app.services.equipment_service.publish_notification", return_value=True),
        }
        self.mocks = {name: item.start() for name, item in self.patches.items()}

    def tearDown(self):
        for item in self.patches.values():
            item.stop()
        super().tearDown()

    def ask(self, quantity=2, authorization=TOKEN):
        return self.service.create_request(
            EquipmentRequestCreate(
                eventId="e1", equipmentId=self.projector, quantity=quantity, startsAt=START, endsAt=END,
                technicalRequirements="HDMI",
            ),
            "u-coord",
            authorization,
        )

    def set_request(self, request_id, **fields):
        row = self.db.get(EquipmentRequest, request_id)
        for name, value in fields.items():
            setattr(row, name, value)
        self.db.commit()

    def published(self):
        """(trigger, context) of every notice sent, in order."""
        return [(call.args[0], call.args[4]) for call in self.mocks["publish"].call_args_list]


class TestNewRequest(NoticeCase):
    def test_every_technical_support_member_is_told_a_request_is_waiting(self):
        request = self.ask()

        self.mocks["publish"].assert_called_once_with(
            "equipment.requested",
            "e1",
            f"e1:equipment.requested:{request.requestId}",
            TECHS,
            {"eventName": "AI Summit", "equipment": "2 × Projector"},
            actor_id="u-coord",
            resource={"type": "equipment_request", "id": request.requestId},
        )
        self.mocks["event"].assert_called_once_with("e1", TOKEN)

    def test_an_event_that_cannot_be_read_is_named_by_its_id(self):
        self.mocks["event"].return_value = None

        self.ask()

        self.assertEqual(self.published()[0][1]["eventName"], "e1")

    def test_a_request_made_without_a_signed_in_user_sends_nothing(self):
        self.ask(authorization=None)

        self.mocks["publish"].assert_not_called()
        self.mocks["techs"].assert_not_called()

    def test_with_no_one_in_technical_support_the_event_is_not_even_read(self):
        self.mocks["techs"].return_value = []

        self.ask()

        self.mocks["event"].assert_not_called()
        self.mocks["publish"].assert_not_called()


class TestChangedRequest(NoticeCase):
    def test_a_refined_quantity_says_what_it_changed_from_and_to(self):
        request = self.ask()
        self.mocks["publish"].reset_mock()

        self.service.refine_request(request.requestId, 3, None, "u-coord", TOKEN)

        self.assertEqual(
            self.published(),
            [("equipment.request_changed", {"eventName": "AI Summit", "equipment": "3 × Projector", "change": "quantity 2 to 3"})],
        )

    def test_refined_requirements_and_quantity_are_both_listed(self):
        request = self.ask()
        self.mocks["publish"].reset_mock()

        self.service.refine_request(request.requestId, 4, "HDMI and VGA", "u-coord", TOKEN)

        self.assertEqual(self.published()[0][1]["change"], "quantity 2 to 4; technical requirements updated")

    def test_a_refinement_that_changes_nothing_sends_nothing(self):
        request = self.ask()
        self.mocks["publish"].reset_mock()

        self.service.refine_request(request.requestId, 2, "HDMI", "u-coord", TOKEN)
        self.service.refine_request(request.requestId, None, None, "u-coord", TOKEN)

        self.mocks["publish"].assert_not_called()

    def test_each_change_is_its_own_notice(self):
        request = self.ask()
        self.service.refine_request(request.requestId, 3, None, "u-coord", TOKEN)
        self.service.refine_request(request.requestId, 4, None, "u-coord", TOKEN)

        occurrences = [call.args[2] for call in self.mocks["publish"].call_args_list[1:]]
        self.assertEqual(len(set(occurrences)), 2)
        self.assertTrue(all(item.startswith("e1:equipment.request_changed:") for item in occurrences))

    def test_a_request_sent_back_for_review_says_so_with_any_new_quantity(self):
        request = self.ask()
        self.set_request(request.requestId, status="rejected")
        self.service.amend_request(request.requestId, None, "u-coord", TOKEN)
        self.set_request(request.requestId, status="rejected")
        self.service.amend_request(request.requestId, 5, "u-coord", TOKEN)

        self.assertEqual(
            [context["change"] for _trigger, context in self.published()[1:]],
            ["sent back for review", "sent back for review with quantity 2 to 5"],
        )

    def test_an_accepted_shortfall_says_how_many_were_short(self):
        partly = self.ask(quantity=3)
        none = self.ask(quantity=2)
        self.set_request(partly.requestId, status="partial", shortfall=1)
        self.set_request(none.requestId, status="unavailable")

        self.service.accept_shortfall(partly.requestId, COORDINATOR, TOKEN)
        self.service.accept_shortfall(none.requestId, COORDINATOR, TOKEN)

        self.assertEqual(
            [context["change"] for _trigger, context in self.published()[2:]],
            [
                "the coordinator accepted the shortfall of 1, so it is resolved",
                "the coordinator accepted the shortfall of 2, so it is resolved",
            ],
        )


class TestRoutesPassTheCaller(NoticeCase):
    """The routes hand the coordinator's token and id on, so their actions notify."""

    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.route_patches = [
            patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR),
            patch("app.routers.equipment.fetch_event_coordinator", return_value=COORDINATOR["userId"]),
        ]
        for item in self.route_patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.route_patches):
            item.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def call(self, method, path, body):
        response = self.client.request(method, path, headers={"Authorization": TOKEN}, json=body)
        self.assertIn(response.status_code, (200, 201), response.text)
        return response.json()

    def test_request_refine_resubmit_and_accept_each_notify_as_the_coordinator(self):
        created = self.call(
            "POST",
            "/equipment/requests",
            {"eventId": "e1", "equipmentId": self.projector, "quantity": 2, "startsAt": START.isoformat(), "endsAt": END.isoformat()},
        )
        request_id = created["requestId"]
        self.call("PATCH", f"/equipment/requests/{request_id}/details", {"quantity": 3})
        self.set_request(request_id, status="rejected")
        self.call("PATCH", f"/equipment/requests/{request_id}", {"resubmit": True})
        self.set_request(request_id, status="unavailable")
        self.call("POST", f"/equipment/requests/{request_id}/accept-shortfall", None)

        calls = self.mocks["publish"].call_args_list
        self.assertEqual(
            [call.args[0] for call in calls],
            ["equipment.requested"] + ["equipment.request_changed"] * 3,
        )
        self.assertEqual({call.kwargs["actor_id"] for call in calls}, {COORDINATOR["userId"]})
        self.assertEqual({call.args[1] for call in self.mocks["event"].call_args_list}, {TOKEN})


class TestTechnicalSupportRecipients(EquipmentCase):
    def users_reply(self, status_code=200, body=None):
        reply = MagicMock(status_code=status_code)
        reply.json.return_value = body or []
        return patch("app.orchestration.clients.httpx.get", return_value=reply)

    def test_everyone_in_technical_support_is_a_recipient(self):
        with self.users_reply(body=[{"userId": "u4", "role": "techsupport"}, {"userId": "u12", "role": "techsupport"}]) as get:
            recipients = technical_support_recipients()

        self.assertEqual(recipients, TECHS)
        self.assertEqual(get.call_args.kwargs["params"], {"roles": "techsupport"})

    def test_no_one_is_told_when_user_service_refuses_or_cannot_be_reached(self):
        with self.users_reply(status_code=403):
            self.assertEqual(technical_support_recipients(), [])
        with patch("app.orchestration.clients.httpx.get", side_effect=httpx.ConnectError("down")):
            self.assertEqual(technical_support_recipients(), [])
