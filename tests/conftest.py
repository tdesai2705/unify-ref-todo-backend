import time

import pytest


@pytest.fixture(autouse=True)
def _realistic_test_duration():
    """Smart Tests' confidence model can't build a useful duration signal when every
    test finishes in a few milliseconds (see Naoto/Samyak's diagnosis on 2026-07-09).
    This adds a uniform artificial delay so PTS has a real cost signal to weigh
    against subset-selection risk. Remove once real-world test suites are slow
    enough on their own, or once this is no longer needed for the demo.
    """
    time.sleep(0.5)
