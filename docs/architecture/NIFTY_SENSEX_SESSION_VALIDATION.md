# NIFTY/SENSEX Session Validation

The additive validator uses injected clocks/calendars and Asia/Kolkata time. Regular baseline is 09:15–15:30; pre-open begins at 09:00 and has explicit order-entry, matching, and buffer phases. Weekends, known holidays, stale/future timestamps, invalid identity, and ambiguous special sessions fail closed.

The calendar is caller-supplied: empty calendars are warned in lenient analysis and blocked for strict execution. No runtime holiday scraping, provider/broker call, or permanent annual holiday list is used.
