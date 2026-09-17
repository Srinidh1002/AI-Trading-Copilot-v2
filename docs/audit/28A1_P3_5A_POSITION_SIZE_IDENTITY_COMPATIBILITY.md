# P3-5A1 position-size blocked identity compatibility

`PositionSizeResultV1` now permits absent selected-contract identity only for
non-approved outcomes. This lets a future sizing service return an honest
blocked result for an incomplete trade plan without inventing identifiers.
Approved results remain strict and execution remains prohibited.
