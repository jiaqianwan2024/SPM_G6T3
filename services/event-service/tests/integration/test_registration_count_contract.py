"""Consumer side of the registration-count contract (see the provider's test).

The real event-service client runs against a fake registration-service that replies with
exactly the body recorded in shared/testing/contracts/registration_count.json.
"""

import json
import unittest
from pathlib import Path

import httpx

from app.orchestration import clients

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[4] / "shared/testing/contracts/registration_count.json").read_text()
)


class TestRegistrationCountContract(unittest.TestCase):
    def setUp(self):
        self.seen = []

        def provider(request: httpx.Request) -> httpx.Response:
            self.seen.append(request)
            return httpx.Response(CONTRACT["response"]["status"], json=CONTRACT["response"]["body"])

        original = clients._registration_client
        clients._registration_client = httpx.Client(transport=httpx.MockTransport(provider))
        self.addCleanup(setattr, clients, "_registration_client", original)

    def test_client_sends_the_agreed_request_and_reads_the_agreed_body(self):
        event_id = CONTRACT["request"]["query"]["eventId"]

        count = clients.registration_count(event_id)

        self.assertEqual(count, CONTRACT["response"]["body"]["count"])
        (request,) = self.seen
        self.assertEqual((request.method, request.url.path), (CONTRACT["request"]["method"], CONTRACT["request"]["path"]))
        self.assertEqual(request.url.params["eventId"], event_id)

    def test_strict_count_used_for_capacity_checks_reads_the_same_body(self):
        # current_registration_count() is not best-effort; it must parse the same contract.
        from unittest.mock import patch

        real_client = httpx.Client
        with patch("app.orchestration.clients.httpx.Client", lambda *a, **k: real_client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=CONTRACT["response"]["body"])), **k)):
            self.assertEqual(
                clients.current_registration_count(CONTRACT["request"]["query"]["eventId"], None),
                CONTRACT["response"]["body"]["count"],
            )
