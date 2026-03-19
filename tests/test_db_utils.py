import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.db_utils import is_kuzu_lock_error, with_kuzu_retry


class DbUtilsTests(unittest.TestCase):
    def test_is_kuzu_lock_error_detects_lock_message(self):
        error = RuntimeError("IO exception: Could not set lock on file")
        self.assertTrue(is_kuzu_lock_error(error))

    def test_with_kuzu_retry_retries_then_succeeds(self):
        attempts = {"count": 0}

        @with_kuzu_retry(operation_name="test op", max_retries=3, initial_delay=0.0)
        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("Could not set lock on file")
            return "ok"

        self.assertEqual(flaky(), "ok")
        self.assertEqual(attempts["count"], 3)


if __name__ == "__main__":
    unittest.main()
