"""Static primary-source catalog for P8C authoritative market events.

URLs are metadata only.  This module performs no network access.
"""

from __future__ import annotations

from services.contracts.authoritative_event_v2 import (
    AuthoritativeEventSourceV2,
)


AUTHORITATIVE_EVENT_SOURCES = (
    AuthoritativeEventSourceV2(
        source_id="RBI",
        display_name="Reserve Bank of India",
        source_class="CENTRAL_BANK",
        jurisdiction="IN",
        domain="rbi.org.in",
        official_url="https://www.rbi.org.in/",
        supported_event_types=(
            "CENTRAL_BANK_POLICY",
            "CENTRAL_BANK_MINUTES",
            "CENTRAL_BANK_SPEECH",
            "GOVERNMENT_NOTICE",
        ),
        default_markets=(
            "NIFTY",
            "SENSEX",
            "GOLDM",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="MOSPI",
        display_name="Ministry of Statistics and Programme Implementation",
        source_class="GOVERNMENT_STATISTICS",
        jurisdiction="IN",
        domain="mospi.gov.in",
        official_url="https://www.mospi.gov.in/release-calendar",
        supported_event_types=(
            "INFLATION_RELEASE",
            "GDP_RELEASE",
            "INDUSTRIAL_PRODUCTION",
            "EMPLOYMENT_RELEASE",
        ),
        default_markets=(
            "NIFTY",
            "SENSEX",
            "GOLDM",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="SEBI",
        display_name="Securities and Exchange Board of India",
        source_class="REGULATOR",
        jurisdiction="IN",
        domain="sebi.gov.in",
        official_url="https://www.sebi.gov.in/",
        supported_event_types=(
            "REGULATORY_CIRCULAR",
            "POSITION_LIMIT_CHANGE",
            "SURVEILLANCE_ACTION",
            "GOVERNMENT_NOTICE",
        ),
        default_markets=(
            "NIFTY",
            "SENSEX",
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        ),
    ),
    AuthoritativeEventSourceV2(
        source_id="NSE",
        display_name="National Stock Exchange of India",
        source_class="EXCHANGE",
        jurisdiction="IN",
        domain="nseindia.com",
        official_url="https://www.nseindia.com/",
        supported_event_types=(
            "EXCHANGE_CIRCULAR",
            "COMPANY_DISCLOSURE",
            "EARNINGS_RESULT",
            "CORPORATE_ACTION",
            "INDEX_REBALANCE",
            "TRADING_HOLIDAY",
            "CONTRACT_SPEC_CHANGE",
            "POSITION_LIMIT_CHANGE",
            "SURVEILLANCE_ACTION",
        ),
        default_markets=(
            "NIFTY",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="BSE",
        display_name="BSE Limited",
        source_class="EXCHANGE",
        jurisdiction="IN",
        domain="bseindia.com",
        official_url="https://www.bseindia.com/",
        supported_event_types=(
            "EXCHANGE_CIRCULAR",
            "COMPANY_DISCLOSURE",
            "EARNINGS_RESULT",
            "CORPORATE_ACTION",
            "INDEX_REBALANCE",
            "TRADING_HOLIDAY",
            "CONTRACT_SPEC_CHANGE",
            "POSITION_LIMIT_CHANGE",
            "SURVEILLANCE_ACTION",
        ),
        default_markets=(
            "SENSEX",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="MCX",
        display_name="Multi Commodity Exchange of India",
        source_class="EXCHANGE",
        jurisdiction="IN",
        domain="mcxindia.com",
        official_url="https://www.mcxindia.com/",
        supported_event_types=(
            "EXCHANGE_CIRCULAR",
            "TRADING_HOLIDAY",
            "CONTRACT_SPEC_CHANGE",
            "POSITION_LIMIT_CHANGE",
            "SURVEILLANCE_ACTION",
        ),
        default_markets=(
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="FEDERAL_RESERVE",
        display_name="Federal Reserve Board",
        source_class="CENTRAL_BANK",
        jurisdiction="US",
        domain="federalreserve.gov",
        official_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        supported_event_types=(
            "CENTRAL_BANK_POLICY",
            "CENTRAL_BANK_MINUTES",
            "CENTRAL_BANK_SPEECH",
        ),
        default_markets=(
            "NIFTY",
            "SENSEX",
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="BLS",
        display_name="U.S. Bureau of Labor Statistics",
        source_class="GOVERNMENT_STATISTICS",
        jurisdiction="US",
        domain="bls.gov",
        official_url="https://www.bls.gov/schedule/",
        supported_event_types=(
            "INFLATION_RELEASE",
            "EMPLOYMENT_RELEASE",
        ),
        default_markets=(
            "NIFTY",
            "SENSEX",
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="BEA",
        display_name="U.S. Bureau of Economic Analysis",
        source_class="GOVERNMENT_STATISTICS",
        jurisdiction="US",
        domain="bea.gov",
        official_url="https://www.bea.gov/news/schedule",
        supported_event_types=(
            "GDP_RELEASE",
            "INFLATION_RELEASE",
            "OTHER_OFFICIAL",
        ),
        default_markets=(
            "NIFTY",
            "SENSEX",
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="EIA",
        display_name="U.S. Energy Information Administration",
        source_class="ENERGY_STATISTICS",
        jurisdiction="US",
        domain="eia.gov",
        official_url="https://www.eia.gov/reports/upcoming.php",
        supported_event_types=(
            "COMMODITY_INVENTORY",
            "NATGAS_STORAGE",
            "OIL_MARKET_REPORT",
            "OTHER_OFFICIAL",
        ),
        default_markets=(
            "CRUDEOILM",
            "NATGASMINI",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="CFTC",
        display_name="U.S. Commodity Futures Trading Commission",
        source_class="DERIVATIVES_REGULATOR",
        jurisdiction="US",
        domain="cftc.gov",
        official_url="https://www.cftc.gov/",
        supported_event_types=(
            "POSITIONING_REPORT",
            "REGULATORY_CIRCULAR",
        ),
        default_markets=(
            "CRUDEOILM",
            "GOLDM",
            "NATGASMINI",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="OPEC",
        display_name="Organization of the Petroleum Exporting Countries",
        source_class="INTERNATIONAL_ORGANIZATION",
        jurisdiction="GLOBAL",
        domain="opec.org",
        official_url="https://www.opec.org/",
        supported_event_types=(
            "OIL_MARKET_REPORT",
            "OTHER_OFFICIAL",
        ),
        default_markets=(
            "CRUDEOILM",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="IEA",
        display_name="International Energy Agency",
        source_class="INTERNATIONAL_ORGANIZATION",
        jurisdiction="GLOBAL",
        domain="iea.org",
        official_url="https://www.iea.org/",
        supported_event_types=(
            "OIL_MARKET_REPORT",
            "OTHER_OFFICIAL",
        ),
        default_markets=(
            "CRUDEOILM",
            "NATGASMINI",
        ),
        schedule_capability=True,
    ),
    AuthoritativeEventSourceV2(
        source_id="DGFT",
        display_name="Directorate General of Foreign Trade",
        source_class="GOVERNMENT_POLICY",
        jurisdiction="IN",
        domain="dgft.gov.in",
        official_url="https://www.dgft.gov.in/",
        supported_event_types=(
            "IMPORT_EXPORT_POLICY",
            "GOVERNMENT_NOTICE",
        ),
        default_markets=(),
    ),
    AuthoritativeEventSourceV2(
        source_id="CBIC",
        display_name="Central Board of Indirect Taxes and Customs",
        source_class="GOVERNMENT_POLICY",
        jurisdiction="IN",
        domain="cbic.gov.in",
        official_url="https://www.cbic.gov.in/",
        supported_event_types=(
            "TAX_DUTY_POLICY",
            "IMPORT_EXPORT_POLICY",
            "GOVERNMENT_NOTICE",
        ),
        default_markets=(),
    ),
    AuthoritativeEventSourceV2(
        source_id="PIB",
        display_name="Press Information Bureau",
        source_class="GOVERNMENT_POLICY",
        jurisdiction="IN",
        domain="pib.gov.in",
        official_url="https://pib.gov.in/",
        supported_event_types=(
            "GOVERNMENT_NOTICE",
            "OTHER_OFFICIAL",
        ),
        default_markets=(),
    ),
)


SOURCE_BY_ID = {
    source.source_id: source
    for source in AUTHORITATIVE_EVENT_SOURCES
}


def get_authoritative_event_source(
    source_id: object,
) -> AuthoritativeEventSourceV2:
    if not isinstance(
        source_id,
        str,
    ):
        raise ValueError(
            "source_id is required."
        )

    normalized = "_".join(
        source_id.strip().upper().split()
    )

    try:
        return SOURCE_BY_ID[
            normalized
        ]
    except KeyError as exc:
        raise ValueError(
            "Unknown authoritative event source."
        ) from exc


def list_authoritative_event_sources(
) -> tuple[
    AuthoritativeEventSourceV2,
    ...,
]:
    return AUTHORITATIVE_EVENT_SOURCES
