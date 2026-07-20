from services.confidence_engine import calculate_confidence

print("=" * 30)
print("CONFIDENCE ENGINE TEST")
print("=" * 30)

confidence = calculate_confidence(
    trend="Bullish",
    momentum="Bullish",
    strength="Very Strong",
    pattern_score=15,
)

print("Confidence:", confidence)