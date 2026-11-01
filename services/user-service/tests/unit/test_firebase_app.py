import threading
import time
import unittest
from unittest.mock import patch

from shared.auth import tokens


class TestFirebaseApp(unittest.TestCase):
    def setUp(self):
        self.saved = tokens._firebase_app
        tokens._firebase_app = None

    def tearDown(self):
        tokens._firebase_app = self.saved

    def test_requests_arriving_together_on_a_new_service_share_one_firebase_app(self):
        # A page opening several requests at once used to initialise the app once
        # per request, and all but the first came back as "Invalid or expired token".
        calls = []

        def initialize():
            calls.append(1)
            time.sleep(0.05)
            return object()

        apps, errors = [], []

        def first_request():
            try:
                apps.append(tokens.get_firebase_app())
            except Exception as exc:
                errors.append(exc)

        with patch.object(tokens, "_initialize_firebase_app", side_effect=initialize):
            threads = [threading.Thread(target=first_request) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(len({id(app) for app in apps}), 1)
