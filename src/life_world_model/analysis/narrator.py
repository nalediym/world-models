from __future__ import annotations

from life_world_model.types import Pattern


def narrate_patterns(
    patterns: list[Pattern], llm_provider: str | None = None
) -> str:
    """Convert patterns to human-readable text.

    Uses LLM if available, plain text otherwise.
    Statistics discover patterns. LLM only translates. NEVER let the LLM
    invent patterns not supported by the data.
    """
    if not patterns:
        return "No patterns discovered from the available data."

    if llm_provider is not None:
        return _narrate_with_llm(patterns, llm_provider)

    return _narrate_plain(patterns)


def _narrate_plain(patterns: list[Pattern]) -> str:
    """Generate a plain-text summary from pattern evidence."""
    sections: dict[str, list[str]] = {}
    for p in patterns:
        sections.setdefault(p.category, []).append(p)

    lines: list[str] = []
    lines.append("== Behavioral Pattern Report ==\n")

    category_titles = {
        "routine": "Daily Routines",
        "correlation": "Activity Correlations",
        "rhythm": "Circadian Rhythm",
        "trigger": "Triggers & Recovery",
        "time_sink": "Time Sinks",
    }

    for category, title in category_titles.items():
        if category not in sections:
            continue
        lines.append(f"\n--- {title} ---")
        for p in sections[category]:
            lines.append(f"  {p.name}: {p.description}")

    lines.append(f"\nTotal patterns discovered: {len(patterns)}")
    return "\n".join(lines)


def _narrate_with_llm(patterns: list[Pattern], llm_provider: str) -> str:
    """Send pattern evidence to an LLM for natural-language narration."""
    # Serialize pattern evidence for the prompt
    evidence_lines: list[str] = []
    for p in patterns:
        evidence_lines.append(
            f"- [{p.category}] {p.name}: {p.description} "
            f"(confidence: {p.confidence:.0%}, evidence: {p.evidence})"
        )
    evidence_text = "\n".join(evidence_lines)

    prompt = (
        "Translate these behavioral patterns into clear, actionable insights. "
        "Include specific numbers from the evidence. "
        "Do not invent patterns not supported by the data.\n\n"
        f"Patterns:\n{evidence_text}"
    )

    if llm_provider == "gemini":
        return _call_gemini(prompt)
    if llm_provider == "mlx":
        return _call_mlx(prompt)

    # Unknown provider — fall back to plain text
    return _narrate_plain(patterns)


def _call_gemini(prompt: str) -> str:
    """Call Gemini API for narration."""
    import os

    try:
        from google import genai  # type: ignore[import-untyped]
    except ImportError:
        return "(Gemini SDK not installed. Falling back to plain text.)"

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "(GEMINI_API_KEY not set. Falling back to plain text.)"

    client = genai.Client(api_key=api_key)
    model = os.getenv("LWM_LLM_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text or "(No response from Gemini.)"


def _call_mlx(prompt: str) -> str:
    """Call local MLX model for narration."""
    try:
        from mlx_lm import generate, load  # type: ignore[import-untyped]
    except ImportError:
        return "(mlx-lm not installed. Falling back to plain text.)"

    import os

    model_name = os.getenv("LWM_LLM_MODEL", "mlx-community/Mistral-7B-Instruct-v0.3-4bit")
    model, tokenizer = load(model_name)
    response = generate(model, tokenizer, prompt=prompt, max_tokens=1024)
    return response
