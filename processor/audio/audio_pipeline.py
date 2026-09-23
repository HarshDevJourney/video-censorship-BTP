"""
Default profanity wordlist. Kept intentionally small/generic — extend or
replace with a maintained list (e.g. a CSV loaded at startup) for production.
Matching is case-insensitive and strips basic punctuation.
"""
DEFAULT_PROFANITY_WORDS = {
    "damn", "hell", "crap", "bastard", "bitch", "asshole",
    "shit", "fuck", "fucking", "bullshit", "piss",
}
