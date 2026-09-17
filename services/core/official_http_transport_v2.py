"""Constrained read-only HTTPS transport for official event sources.

GET only.  No authentication, cookies, POSTs, trading-provider access,
order authority, or certification semantics exist here.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import (
    urljoin,
    urlparse,
)

import requests


def _normalize_domain(
    value: object,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            "Domain must be a string."
        )

    domain = value.strip().lower()

    if not domain:
        raise ValueError(
            "Domain cannot be empty."
        )

    return domain


def _allowed_host(
    host: str,
    allowed_domains: tuple[
        str,
        ...,
    ],
) -> bool:
    host = host.lower()

    return any(
        host == domain
        or host.endswith(
            "." + domain
        )
        for domain in allowed_domains
    )


@dataclass(slots=True)
class OfficialHttpTextTransportV2:
    allowed_domains: tuple[
        str,
        ...,
    ]

    timeout_seconds: float = 10.0
    max_bytes: int = 2_000_000
    max_redirects: int = 3

    user_agent: str = (
        "AI-Trading-Copilot/"
        "AuthoritativeEventReader-V2"
    )

    session: object | None = None

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.allowed_domains,
            tuple,
        ):
            raise ValueError(
                "allowed_domains must be a tuple."
            )

        normalized = tuple(
            _normalize_domain(
                value
            )
            for value
            in self.allowed_domains
        )

        if not normalized:
            raise ValueError(
                "At least one allowed domain is required."
            )

        if len(
            set(
                normalized
            )
        ) != len(
            normalized
        ):
            raise ValueError(
                "Duplicate allowed domains."
            )

        if (
            not isinstance(
                self.timeout_seconds,
                (int, float),
            )
            or isinstance(
                self.timeout_seconds,
                bool,
            )
            or self.timeout_seconds <= 0
        ):
            raise ValueError(
                "timeout_seconds must be positive."
            )

        if (
            not isinstance(
                self.max_bytes,
                int,
            )
            or isinstance(
                self.max_bytes,
                bool,
            )
            or self.max_bytes <= 0
        ):
            raise ValueError(
                "max_bytes must be positive."
            )

        if (
            not isinstance(
                self.max_redirects,
                int,
            )
            or isinstance(
                self.max_redirects,
                bool,
            )
            or self.max_redirects < 0
        ):
            raise ValueError(
                "max_redirects must be non-negative."
            )

        object.__setattr__(
            self,
            "allowed_domains",
            normalized,
        )

    def _validate_url(
        self,
        url: object,
    ) -> str:
        if not isinstance(
            url,
            str,
        ):
            raise ValueError(
                "URL must be a string."
            )

        url = url.strip()

        parsed = urlparse(
            url
        )

        if (
            parsed.scheme.lower()
            != "https"
        ):
            raise ValueError(
                "Official transport requires HTTPS."
            )

        host = (
            parsed.hostname
            or ""
        ).lower()

        if not host:
            raise ValueError(
                "Official transport URL requires a host."
            )

        if not _allowed_host(
            host,
            self.allowed_domains,
        ):
            raise ValueError(
                "Official transport host is not allowlisted."
            )

        return url

    def fetch_text(
        self,
        url: str,
        *,
        accepted_content_types: tuple[
            str,
            ...,
        ] = (
            "text/html",
            "text/plain",
            "text/calendar",
        ),
    ) -> str:
        current_url = self._validate_url(
            url
        )

        client = (
            self.session
            if self.session is not None
            else requests
        )

        accepted = tuple(
            value.lower()
            for value
            in accepted_content_types
        )

        for redirect_index in range(
            self.max_redirects + 1
        ):
            response = client.get(
                current_url,
                headers={
                    "User-Agent":
                    self.user_agent,
                    "Accept":
                    ", ".join(
                        accepted
                    ),
                },
                timeout=float(
                    self.timeout_seconds
                ),
                allow_redirects=False,
            )

            status = int(
                response.status_code
            )

            if 300 <= status < 400:
                location = (
                    response.headers
                    .get(
                        "Location"
                    )
                )

                if not location:
                    raise RuntimeError(
                        "Redirect response has no Location header."
                    )

                if (
                    redirect_index
                    >= self.max_redirects
                ):
                    raise RuntimeError(
                        "Official transport redirect limit exceeded."
                    )

                redirected = urljoin(
                    current_url,
                    location,
                )

                current_url = (
                    self._validate_url(
                        redirected
                    )
                )

                continue

            if not 200 <= status < 300:
                raise RuntimeError(
                    "Official source HTTP request failed "
                    f"with status {status}."
                )

            content_type = (
                response.headers
                .get(
                    "Content-Type",
                    "",
                )
                .split(
                    ";",
                    1,
                )[0]
                .strip()
                .lower()
            )

            if (
                accepted
                and content_type
                and content_type
                not in accepted
            ):
                raise RuntimeError(
                    "Unexpected official-source content type: "
                    f"{content_type}"
                )

            raw = response.content

            if not isinstance(
                raw,
                (bytes, bytearray),
            ):
                raise RuntimeError(
                    "Official-source response content must be bytes."
                )

            if len(
                raw
            ) > self.max_bytes:
                raise RuntimeError(
                    "Official-source response exceeds size limit."
                )

            encoding = (
                getattr(
                    response,
                    "encoding",
                    None,
                )
                or "utf-8"
            )

            return bytes(
                raw
            ).decode(
                encoding,
                errors="strict",
            )

        raise RuntimeError(
            "Official transport exhausted redirect processing."
        )
