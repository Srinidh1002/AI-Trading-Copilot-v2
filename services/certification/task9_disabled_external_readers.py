"""Provider-disabled Task 9 external readers.

These readers deliberately perform no network calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.contracts.task9_external_provider_state_v1 import (
    Task9ExternalProviderDomain,
    Task9ExternalProviderSnapshotV1,
)


@dataclass(frozen=True, slots=True)
class Task9DisabledExternalReadersV1:
    provider_snapshot: Task9ExternalProviderSnapshotV1

    def __post_init__(self):
        if (
            type(self.provider_snapshot)
            is not Task9ExternalProviderSnapshotV1
        ):
            raise TypeError("provider_snapshot")

    def _assert_disabled(
        self,
        domain: Task9ExternalProviderDomain,
    ):
        state = self.provider_snapshot.for_domain(
            domain
        )

        if (
            state.provider_selected is not False
            or state.network_calls_allowed is not False
            or state.availability is not False
        ):
            raise ValueError(
                "TASK9_EXTERNAL_READER_STATE_NOT_DISABLED"
            )

        return state

    def read_market_breadth(self):
        state = self._assert_disabled(
            Task9ExternalProviderDomain.MARKET_BREADTH
        )
        return state, None

    def read_institutional_flow(self):
        state = self._assert_disabled(
            Task9ExternalProviderDomain.FII_DII
        )
        return state, None

    def read_scheduled_events(self):
        state = self._assert_disabled(
            Task9ExternalProviderDomain.ECONOMIC_EVENTS
        )
        return state, ()

    def read_global_markets(self):
        state = self._assert_disabled(
            Task9ExternalProviderDomain.GLOBAL_MARKETS
        )
        return state, ()

    def read_structured_news(self):
        state = self._assert_disabled(
            Task9ExternalProviderDomain.STRUCTURED_NEWS
        )
        return state, ()


__all__ = (
    "Task9DisabledExternalReadersV1",
)
