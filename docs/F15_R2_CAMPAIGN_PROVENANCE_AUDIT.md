
# F15-R2 Campaign/Policy Provenance Audit

**Phase:** R2-29 (audit-only, no code change)
**Scope:** What provenance every newly opened trade retains today
**Output class:** Documentation. No state writes. No strategy change.
**Status:** Complete.

---

## 1. Purpose

Mission R2-29 requires that every newly opened trade retains at least:

- market
- trade_id
- strategy_version
- certification_epoch
- certification_schema_version
- entry timestamp
- prediction fingerprint
- provider

If a canonical campaign identifier exists, retain it. If none exists,
document the gap for Brain-VNext / B10 rather than inventing one on this
branch.

---

## 2. Index trade provenance (src/target_focused_bot.py)

Every entry written by try_open (line ~1883 region) contains:

| Field                        | Present | Source                          |
|------------------------------|---------|---------------------------------|
| market                       | YES     | self.market                     |
| trade_id                     | YES     | make_trade_id(self.market)      |
| strategy_version             | YES     | self.strategy_version           |
| certification_epoch          | YES     | self.certification_epoch        |
| certification_schema_version | YES     | self.certification_schema_version |
| entry_time                   | YES     | datetime.now()                  |
| prediction_fingerprint       | YES     | self._last_prediction_fingerprint |
| provider                     | NO      | not stored on the trade dict    |
| campaign_id                  | NO      | no canonical campaign id exists |

Bonus provenance also stored: execution_mode, broker_submission,
live_execution, certification_eligible, certification_trade_date,
certification_regime, market_phase_at_entry, certification_session_phase,
first_touch_result, entry_spot.

**Gap:** provider and campaign_id are absent from the index trade dict.
provider is implicitly FYERS via the runtime bundle and is not currently
required for certification counting.

---

## 3. MCX position provenance (src/mcx/mcx_paper_bot.py)

Every entry written by try_open (line ~711 region) contains:

| Field                        | Present | Source                          |
|------------------------------|---------|---------------------------------|
| product                      | YES     | PRODUCT                         |
| trade_id                     | YES     | make_trade_id(PRODUCT)          |
| strategy_version             | YES     | get_product_epochs(PRODUCT)     |
| epoch_id                     | YES     | get_product_epochs(PRODUCT)     |
| certification_schema_version | NO      | not stored on the position dict |
| entry_time                   | YES     | datetime.now().isoformat(...)   |
| prediction_fingerprint       | NO      | not stored on the position dict |
| provider                     | NO      | not stored on the position dict |
| campaign_id                  | NO      | no canonical campaign id exists |

Bonus provenance also stored: certification_eligible, lots, lot_size,
cash_multiplier, entry_ltp, strike, type, symbol, token.

**Gap:** MCX is missing certification_schema_version,
prediction_fingerprint, provider, and campaign_id.

---

## 4. Campaign identity — answer

**No canonical campaign identifier exists in the current repository.**
The closest concept is certification_epoch (index) / epoch_id (MCX),
which identifies the strategy epoch but not the paper-trading campaign
instance.

Mission R2-29 explicitly says:

> If there is no canonical campaign identifier, do not invent a large
> new campaign subsystem tonight. Document the gap for Brain-VNext/B10.

---

## 5. Disposition

- **No code change made in R2-29.** The gap is documented, not patched.
- The R2-2, R2-3, R2-4 fixes did not remove any existing provenance
  field.
- Every newly opened trade after R2 continues to retain the fields it
  retained before R2, plus make_trade_id market scoping.
- Adding provider and campaign_id (and the MCX-side
  certification_schema_version and prediction_fingerprint) is a
  Brain-VNext / B10 design task, not a stabilization repair.

---

## 6. Recommendation for B10

When B10 defines the campaign subsystem:

1. Introduce a campaign_id chosen at supervisor start and threaded
   through every worker's env (same mechanism as
   PAPER_WORKER_GENERATION in R1's heartbeat).
2. Write campaign_id and provider onto every new trade dict at
   try_open, for both index and MCX.
3. Add certification_schema_version and prediction_fingerprint to the
   MCX position dict so MCX certification evidence is provably linked
   to its originating decision.
4. Do not backfill any historical trade with fabricated campaign_id.
   Old trades remain as-is.
