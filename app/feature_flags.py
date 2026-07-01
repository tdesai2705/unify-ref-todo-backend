import os


class FeatureFlags:
    """
    Feature flag abstraction backed by environment variables.

    To enable a flag, set the env var before running:
        export FEATURE_ENHANCED_STATS=true
        export FEATURE_DUE_DATE_WARNINGS=true
        export FEATURE_BULK_OPERATIONS=true

    Swap is_enabled() for a CloudBees Feature Management SDK call
    when CB FM is wired up — the rest of the app stays unchanged.
    """

    @staticmethod
    def is_enabled(flag: str) -> bool:
        return os.environ.get(flag, "false").lower() in ("true", "1", "yes")

    @classmethod
    def enhanced_stats(cls) -> bool:
        """Stats endpoint returns category breakdown + overdue count."""
        return cls.is_enabled("FEATURE_ENHANCED_STATS")

    @classmethod
    def due_date_warnings(cls) -> bool:
        """Todo responses include overdue + days_until_due fields."""
        return cls.is_enabled("FEATURE_DUE_DATE_WARNINGS")

    @classmethod
    def bulk_operations(cls) -> bool:
        """Enables POST /todos/bulk-complete endpoint."""
        return cls.is_enabled("FEATURE_BULK_OPERATIONS")
