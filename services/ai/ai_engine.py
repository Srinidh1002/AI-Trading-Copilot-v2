"""
AI Engine (Local Development)
"""

from services.ai.context_engine import build_context
from services.ai.prompt_engine import build_prompt


def generate_ai_analysis(snapshot, decision):

    context = build_context(snapshot, decision)

    prompt = build_prompt(context)

    return {
        "prompt": prompt,
        "analysis": (
            "LLM not connected yet.\n\n"
            "Prompt generated successfully.\n"
            "Next step: Connect Ollama for local AI."
        ),
    }