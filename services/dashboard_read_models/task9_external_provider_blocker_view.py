"""Read-only Task 9 external-provider blocker projection."""
from __future__ import annotations

from services.certification.task9_external_provider_blocker import Task9ExternalProviderBlockerStore


def read_task9_external_provider_blocker(*, persistence_root, official_run_id):
    """Return an optional safe projection; this path cannot mutate authority."""
    value = Task9ExternalProviderBlockerStore(persistence_root).load(
        official_run_id,
        migrate=False,
    )
    if value is None:
        return None
    projection = {key: value[key] for key in (
        "blocker_code", "status", "provider", "endpoint", "first_seen_at",
        "last_seen_at", "last_probe_at", "last_probe_result",
        "next_probe_not_before", "occurrence_count",
    )}
    if value.get("schema_version") == 2:
        projection.update(
            last_failure_reason=value["last_failure_reason"],
            consecutive_rate_limit_count=value["consecutive_rate_limit_count"],
        )
    return projection
