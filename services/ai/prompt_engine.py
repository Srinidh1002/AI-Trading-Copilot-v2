"""
Prompt Builder
"""


def build_prompt(context):

    return f"""
You are an expert Indian Futures & Options trader.

Current Price:
{context['market']['price']}

Trend:
{context['trend']['trend']}

Momentum:
{context['trend']['momentum']}

Strength:
{context['trend']['strength']}

Support:
{context['support']}

Resistance:
{context['resistance']}

Confidence:
{context['confidence']}%

Trade Status:
{context['trade']['status']}

Explain:

1. Why should the trader BUY / SELL / HOLD?
2. What are the risks?
3. What confirms this setup?
4. What invalidates this setup?
5. Should the trader wait?

Respond in professional trading language.
"""