import os


class FeatureFlags:
    """
    Feature flag abstraction for the CloudBees Unify reference architecture.

    Current backend: environment variables — zero dependencies, works everywhere.

    Upgrade path to CloudBees Feature Management SDK:
    ─────────────────────────────────────────────────
    Replace is_enabled() with:

        from cloudbees.feature_management import FeatureManagement
        _fm = FeatureManagement(sdk_key=os.environ["CB_FM_SDK_KEY"])

        @staticmethod
        def is_enabled(flag: str) -> bool:
            return _fm.variation(flag, context={"env": os.environ.get("FLASK_ENV", "dev")})

    Everything else — routes, tests, Jenkinsfile, PTS mapping — stays identical.
    You gain real-time delivery, per-user targeting, gradual rollout %, and audit log.

    Smart Tests note:
    ─────────────────
    Each flag below maps to a distinct test class in tests/test_feature_flags.py.
    After 20+ observation builds, PTS learns this mapping and selects only the
    relevant test class when code behind a single flag changes.
    """

    @staticmethod
    def is_enabled(flag: str) -> bool:
        return os.environ.get(flag, "false").lower() in ("true", "1", "yes")

    @classmethod
    def enhanced_stats(cls) -> bool:
        """Stats endpoint: adds overdue_count + by_category. → TestEnhancedStats* tests."""
        return cls.is_enabled("FEATURE_ENHANCED_STATS")

    @classmethod
    def due_date_warnings(cls) -> bool:
        """Todo responses: adds overdue + days_until_due fields. → TestDueDateWarnings* tests."""
        return cls.is_enabled("FEATURE_DUE_DATE_WARNINGS")

    @classmethod
    def bulk_operations(cls) -> bool:
        """Enables POST /todos/bulk-complete endpoint. → TestBulkOperations* tests."""
        return cls.is_enabled("FEATURE_BULK_OPERATIONS")
