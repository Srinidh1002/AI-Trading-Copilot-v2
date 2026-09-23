"""One-command daily FYERS authentication bootstrap.

When necessary this opens the official FYERS OAuth page. The user still
completes FYERS login / 2FA. Authorization codes, access tokens and secrets are
never printed.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from services.broker.fyers_auth_v2 import (
    FyersAuthError,
    classify_fyers_response_v2,
)
from services.broker.fyers_daily_auth_v2 import (
    FyersDailyAuthError,
    ensure_fyers_daily_auth_v2,
)
from services.broker.fyers_sdk_data_client_v2 import (
    build_fyers_data_client_v2,
)


def _verify_provider(
    credentials,
) -> None:
    log_path = tempfile.mkdtemp(prefix="fyers-daily-auth-")

    client = build_fyers_data_client_v2(
        client_id=credentials.app_id,
        access_token=credentials.access_token,
        log_path=log_path,
    )

    response = client.quotes({"symbols": ("NSE:NIFTY50-INDEX")})

    error = classify_fyers_response_v2(response)

    if error is not None:
        raise error

    if (
        not isinstance(
            response,
            dict,
        )
        or response.get("s") != "ok"
    ):
        raise FyersDailyAuthError(
            "FYERS provider verification did not return status=ok"
        )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--env-file",
        default=".env",
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
    )

    args = parser.parse_args()

    print("FYERS_DAILY_AUTH_START")

    print("ENV_FILE=" + str(Path(args.env_file)))

    print("TOKEN_VALUES_PRINTED=False")

    try:
        result = ensure_fyers_daily_auth_v2(
            env_file=args.env_file,
            skew_seconds=600,
            force_reauth=args.force,
            timeout_seconds=args.timeout_seconds,
            provider_verify=_verify_provider,
        )

    except (
        FyersAuthError,
        FyersDailyAuthError,
    ) as exc:
        print("FYERS_DAILY_AUTH=HOLD")

        print("ERROR_TYPE=" + type(exc).__name__)

        print(
            "ERROR_REASON="
            + str(
                getattr(
                    exc,
                    "reason_code",
                    str(exc),
                )
            )[:120]
        )

        print("TOKEN_VALUES_PRINTED=False")

        return 1

    print("AUTH_STATUS=" + result.status)

    print("TOKEN_REPLACED=" + str(result.token_replaced))

    print("PROVIDER_VERIFIED=" + str(result.provider_verified))

    print("TOKEN_SECONDS_REMAINING=" + str(result.seconds_remaining))

    print("FYERS_DAILY_AUTH=PASS")

    print("TOKEN_VALUES_PRINTED=False")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
