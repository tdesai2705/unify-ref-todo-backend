# Reference Architecture: Feature Flags + Predictive Test Selection

> **CloudBees Unify — Reference Implementation**
> Shows how CloudBees Feature Management and Smart Tests work together to make CI faster, safer, and smarter with every flag-gated release.

---

## The Core Idea

When developers use feature flags to release code incrementally, they create a natural boundary: **the code behind a flag is only exercised by the tests that cover that flag**.

CloudBees Smart Tests (Predictive Test Selection) learns this mapping automatically. After a short observation period, it knows:

- Change code in `FEATURE_BULK_OPERATIONS` → run the 5 bulk-operations tests, skip the other 30
- Change code in `FEATURE_ENHANCED_STATS` → run the 6 stats tests, not the full suite
- Change core auth code → run all 14 auth tests regardless of flags

**Result: flag-gated PRs get test feedback in seconds instead of minutes, with no reduction in confidence.**

---

## Why This Matters

| Without this integration | With this integration |
|---|---|
| Every PR runs all N tests | Flag-gated PRs run only impacted tests |
| CI time grows linearly with test count | CI time stays flat as test suite grows |
| Devs wait for full suite on a 3-line change | Sub-minute feedback on flag-specific changes |
| Feature flags reduce deployment risk | Feature flags + PTS also reduce CI cost |

In this reference app: **35 tests → as few as 4–6 per flag-gated PR** after 20 observation runs.

---

## Architecture

```
Developer pushes flag-gated change
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  CloudBees CI (CBCI on GKE)                         │
│                                                     │
│  ① record build   — tells Unify about this commit   │
│  ② record session — creates PTS session             │
│  ③ [obs] run all  — OR [subset] PTS selects tests   │
│  ④ record tests   — uploads results to Unify        │
└─────────────────────┬───────────────────────────────┘
                      │ results + git blame
                      ▼
┌─────────────────────────────────────────────────────┐
│  CloudBees Unify (Smart Tests)                      │
│                                                     │
│  Builds confidence model:                           │
│  flag code path ←→ test coverage mapping            │
│                                                     │
│  After 20+ runs: subsetting kicks in                │
│  Selects minimum tests at target confidence %       │
└─────────────────────────────────────────────────────┘
                      │ image tag
                      ▼
┌─────────────────────────────────────────────────────┐
│  Docker Hub → ArgoCD → GKE                         │
│  QA env auto-syncs within 3 minutes                 │
└─────────────────────────────────────────────────────┘
```

---

## Feature Flags in This App

Three flags demonstrate distinct code paths — each maps to a distinct test class:

| Flag (env var) | What it enables | Tests it covers | File |
|---|---|---|---|
| `FEATURE_ENHANCED_STATS` | Stats endpoint adds `overdue_count` + `by_category` | `TestEnhancedStats*` (5 tests) | `routes.py:get_stats()` |
| `FEATURE_DUE_DATE_WARNINGS` | Todo responses add `overdue` + `days_until_due` | `TestDueDateWarnings*` (6 tests) | `routes.py:_todo_dict()` |
| `FEATURE_BULK_OPERATIONS` | Enables `POST /todos/bulk-complete` | `TestBulkOperations*` (7 tests) | `routes.py:bulk_complete()` |

Each flag is also a CBCI pipeline parameter — toggle per build from the UI without code changes.

---

## How the Observation → Subsetting Transition Works

**Phase 1 — Observation (builds 1–20+)**

```
SMART_TESTS_OBSERVATION = true   (pipeline parameter)
```

Every build runs all 35 tests. Unify records which tests ran, which passed/failed, and maps them to the code changed in each commit. The confidence curve rises with each run.

**Phase 2 — Subsetting (build 21+)**

```
SMART_TESTS_OBSERVATION = false
```

The pipeline collects all test IDs, passes them to `smart-tests subset pytest`, and runs only what PTS selects. A commit touching only `FEATURE_BULK_OPERATIONS` code runs ~5 tests instead of 35.

**The demo moment:** change one line in the bulk-complete route, push, watch Unify select 5/35 tests and the build finish in 40 seconds instead of 3 minutes.

---

## Replicating This Pattern (for customers)

1. **Add a `FeatureFlags` class** — thin wrapper over env vars (or your FM SDK). See `app/feature_flags.py`.
2. **Write flag-scoped test classes** — one class per flag, clearly named. See `tests/test_feature_flags.py`.
3. **Add Smart Tests to your Jenkinsfile** — four commands: `record build` → `record session` → run tests → `record tests`. See `Jenkinsfile`.
4. **Add `SMART_TESTS_OBSERVATION` as a pipeline parameter** — keep it `true` for 20+ runs, then flip to `false`.
5. **Watch Unify** — after the observation phase, the subsetting confidence curve shows exactly which tests cover which code paths.

No changes to application logic. No test framework changes. Drop-in addition.

---

## Upgrading to CloudBees Feature Management SDK

The `FeatureFlags` class in this repo is backed by environment variables. To connect it to CloudBees Feature Management (real-time flag delivery, targeting rules, rollout %, audit trail), swap one method:

```python
# Current (env var — works anywhere, zero dependencies)
@staticmethod
def is_enabled(flag: str) -> bool:
    return os.environ.get(flag, "false").lower() in ("true", "1", "yes")

# Upgraded (CloudBees Feature Management SDK)
from cloudbees.feature_management import FeatureManagement

fm = FeatureManagement(sdk_key=os.environ["CB_FM_SDK_KEY"])

@staticmethod
def is_enabled(flag: str) -> bool:
    return fm.variation(flag, context={"env": os.environ.get("FLASK_ENV", "dev")})
```

Everything else — routes.py, tests, Jenkinsfile — stays identical. The flag names stay the same. The PTS mapping stays valid. You get targeting rules, gradual rollout, and audit logs without touching a single test.

---

## Running Tests Locally

```bash
pip install -r requirements.txt

# All tests (observation mode equivalent)
PYTHONPATH=. pytest tests/ -v

# With a specific flag on
FEATURE_BULK_OPERATIONS=true PYTHONPATH=. pytest tests/test_feature_flags.py -v -k Bulk

# With all flags on
FEATURE_ENHANCED_STATS=true \
FEATURE_DUE_DATE_WARNINGS=true \
FEATURE_BULK_OPERATIONS=true \
PYTHONPATH=. pytest tests/ -v
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python Flask 3.0 |
| ORM | SQLAlchemy 2.0 |
| Database | PostgreSQL 15 |
| Tests | pytest 7.4 |
| CI | CloudBees CI (Multibranch Pipeline, GKE agents) |
| Test Intelligence | CloudBees Smart Tests (Predictive Test Selection) |
| Feature Flags | Environment variables → CloudBees FM SDK (upgrade path above) |
| Containers | Docker Hub (`tejasdesai27/todo-backend`) |
| GitOps | ArgoCD → GKE (QA + prod environments) |

---

## Project Structure

```
backend/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── feature_flags.py     # Feature flag abstraction (FM SDK upgrade point)
│   ├── models.py            # SQLAlchemy models (User, Todo)
│   └── routes.py            # API endpoints — flag-gated sections clearly marked
├── tests/
│   ├── test_api.py          # Core API tests (14 tests)
│   └── test_feature_flags.py # Flag-specific tests (21 tests, 3 classes)
├── Jenkinsfile              # CBCI pipeline: Smart Tests + Docker + ArgoCD
├── requirements.txt
└── Dockerfile
```

---

*Part of the [CloudBees Unify Reference Architecture](https://github.com/tdesai2705). Maintained by the PS Lab team.*
