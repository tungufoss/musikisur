import re
import unicodedata


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"\([^)]*(remaster|live|edit|version)[^)]*\)", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def candidate_track_key(artist: str, title: str) -> str:
    return f"{normalize_text(artist)}::{normalize_text(title)}"
