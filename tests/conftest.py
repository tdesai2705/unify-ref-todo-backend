import hashlib
import time

import pytest


@pytest.fixture(autouse=True)
def _realistic_test_duration(request):
    """Smart Tests' confidence model can't build a useful duration signal when every
    test finishes in a few milliseconds (see Naoto/Samyak's diagnosis on 2026-07-09),
    and a flat uniform delay gives the optimizer nothing to actually optimize between
    tests. This derives a deterministic, per-test delay in the 1.5s-4.5s range from
    a hash of the test's node id, so the suite has real duration *variance* (some
    tests look "cheap", some look "expensive") the same way a real-world suite would,
    rather than one flat number repeated for every test.
    """
    digest = hashlib.sha256(request.node.nodeid.encode()).hexdigest()
    delay = 1.5 + (int(digest[:8], 16) % 3000) / 1000.0  # 1.5s - 4.5s
    time.sleep(delay)
