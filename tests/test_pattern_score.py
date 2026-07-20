from services.analysis.pattern_score import pattern_score

print("=" * 30)
print("PATTERN SCORE TEST")
print("=" * 30)

patterns = [
    {"signal": "Bullish"},
    {"signal": "Bearish"},
    {"signal": "Neutral"},
]

for p in patterns:
    print(pattern_score(p))