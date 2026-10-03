"""Run the same local oracle with a route guard deliberately disarmed.

This is synthetic fault injection using unittest.mock, as in the pinned SDK's
tests/test_transport.py. A disarmed check must return 1, then the armed check 0.
"""

import argparse
import unittest
from unittest.mock import patch

import test_worker


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--disarm-route", action="store_true")
    parsed = args.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromName(
        "ConfigurationTests.test_wrong_route_is_rejected_before_a_client_exists",
        test_worker,
    )
    if parsed.disarm_route:
        with patch.object(test_worker.worker, "loopback_root", lambda value: value):
            result = unittest.TextTestRunner(verbosity=2).run(suite)
    else:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
