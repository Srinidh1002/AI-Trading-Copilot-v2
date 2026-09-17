# P3-5A2 position-size blocked direction compatibility

`PositionSizeResultV1` can now preserve an honest non-actionable `WAIT` result
with no option type for non-approved sizing statuses. This supports typed blocked
results from non-ready trade plans without fabricating BUY, SELL, CALL, or PUT.
Approved sizing direction remains strict.
