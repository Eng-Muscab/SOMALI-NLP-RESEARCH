"""
Text cleaning utilities for Somali NLP preprocessing.

TODO (Qof 1):
- Implement `clean_text(text: str) -> str` based on your chosen rules.
- Keep the function deterministic and document the rules in `docs/TEAM_PLAN.md`.
"""

# imports
import re

# regex patterns
URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", re.IGNORECASE)
WS_RE = re.compile(r"\s")

def clean_text(text: str) -> str :
    """
    Text cleaning rules (QOF 1):
    1) handle None/NaN
    2) remove urls/emails
    3) lowercase (optional)
    4) normalize whitespace
    return cleaned text
    5) punctuations
    """
    # 1) handle none
    if text is None :
        return ""
    
    # 2) maku sure it is string
    text = str(text)

    # 3) remove url + email
    text = URL_RE.sub("", text)
    text = EMAIL_RE.sub("", text)

    # 4) lowercase
    text = text.lower()

    # 5) normalize whitespace
    text = WS_RE.sub(" ", text)

    # 6) punctuations
    text = re.sub(r"[^\w\s]", "", text)

    return text

    