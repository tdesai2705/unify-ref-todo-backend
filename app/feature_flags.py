import os
from rox.server.rox_server import Rox
from rox.server.flags.rox_flag import RoxFlag
from rox.server.rox_options import RoxOptions, NetworkConfigurationsOptions


class _Flags:
    def __init__(self):
        self.enhanced_stats = RoxFlag(False)
        self.due_date_warnings = RoxFlag(False)
        self.bulk_operations = RoxFlag(False)


_flags = _Flags()
_setup_done = False


def setup(api_key: str):
    """Connect to CloudBees Feature Management platform.

    Called once at app startup with CASK_API_KEY.
    No-op if key is empty (local dev / tests → falls back to env vars).
    """
    global _setup_done
    if _setup_done or not api_key:
        return
    Rox.register(_flags)
    options = RoxOptions(network_configuration_options=NetworkConfigurationsOptions(
        get_config_api_endpoint='https://api.cloudbees.io/device/get_configuration',
        get_config_cloud_endpoint='https://rox-conf.cloudbees.io',
        send_state_api_endpoint='https://api.cloudbees.io/device/update_state_store',
        send_state_cloud_endpoint='https://rox-state.cloudbees.io',
        analytics_endpoint='https://api.cloudbees.io/events/flag-impressions',
        push_notification_endpoint='https://api.cloudbees.io/sse',
    ))
    Rox.setup(api_key, options).result()
    _setup_done = True


def _env_flag(name: str) -> bool:
    return os.environ.get(name, 'false').lower() in ('true', '1', 'yes')


class FeatureFlags:
    """
    Feature flag abstraction backed by CloudBees Feature Management.

    When CASK_API_KEY is set (production / GKE):
      → Flags are controlled from the Unify FM UI in real time.
        No redeployment needed to toggle a flag.

    When CASK_API_KEY is not set (tests / local dev):
      → Falls back to FEATURE_* environment variables.
        Existing tests and CI runs work unchanged.

    Flag names match exactly what is registered in Unify FM:
      enhanced_stats, due_date_warnings, bulk_operations

    Smart Tests mapping:
      enhanced_stats    → TestEnhancedStats* tests
      due_date_warnings → TestDueDateWarnings* tests
      bulk_operations   → TestBulkOperations* tests
    """

    @classmethod
    def enhanced_stats(cls) -> bool:
        if _setup_done:
            return _flags.enhanced_stats.is_enabled()
        return _env_flag('FEATURE_ENHANCED_STATS')

    @classmethod
    def due_date_warnings(cls) -> bool:
        if _setup_done:
            return _flags.due_date_warnings.is_enabled()
        return _env_flag('FEATURE_DUE_DATE_WARNINGS')

    @classmethod
    def bulk_operations(cls) -> bool:
        if _setup_done:
            return _flags.bulk_operations.is_enabled()
        return _env_flag('FEATURE_BULK_OPERATIONS')
