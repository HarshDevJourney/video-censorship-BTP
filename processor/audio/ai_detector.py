"""
Uses Claude to decide which transcribed words should be censored, instead of
a static wordlist. This catches things a fixed list misses (slurs, sexual
language, context-dependent phrases) and avoids false positives on words
that only look bad out of context.

The model is given the transcript as an indexed word list and asked to return
only the indices that should be censored, as JSON. We never send audio/video,
just the transcript text.
"""
import os
import json

import anthropic

from audio.transcriber import WordTiming

MODEL = os.environ.get("PROFANITY_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = """You are a content-moderation classifier for a video censorship pipeline.

You will be given a transcript as a numbered list of words, in order.

Return ONLY a JSON array of the integer indices of words that should be
censored with a beep because they are profanity, slurs, or explicit sexual
language. Use surrounding words for context (e.g. a word that is only
offensive in certain phrasing).

Do not include mild words unless they are genuinely profane. Do not explain
your answer. Respond with JSON only, e.g. [4, 17, 18, 42]. If nothing should
be censored, respond with []."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def detect_words_to_censor(words: list[WordTiming]) -> set[int]:
    """Returns the set of WordTiming.index values the model flagged for censorship."""
    if not words:
        return set()

    numbered_transcript = "\n".join(f"{w.index}: {w.word}" for w in words)

    response = _client().messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": numbered_transcript}],
    )

    raw_text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()

    try:
        indices = json.loads(raw_text)
        return {int(i) for i in indices}
    except (json.JSONDecodeError, TypeError, ValueError):
        # Fail closed on parse errors: censor nothing rather than guessing,
        # and let the caller log/inspect raw_text if this happens often.
        return set()
