"""Preset profile-photo library.

Deliberately a fixed, server-defined set -- not a file upload. A customer
picks a `key` from this list; nothing is ever written to disk on their
behalf. This keeps the account-editing feature from becoming a second
file-upload attack surface alongside the two that already exist on
purpose/by-design (vulnerable/upload/ and app/services/product_photos.py).
Rendering is pure CSS (gradient class) + a glyph -- no image assets at
all, so there's nothing to store, serve, or validate as a file.

LETTER_AVATAR_KEY is the classic "first letter of your name on a colored
circle" look (what every user had before presets existed) -- kept as an
explicit, selectable option rather than removed, since plenty of people
just want their initial.
"""

PRESET_AVATARS = [
    {"key": "fox", "emoji": "\U0001F98A", "label": "Fox"},
    {"key": "panda", "emoji": "\U0001F43C", "label": "Panda"},
    {"key": "owl", "emoji": "\U0001F989", "label": "Owl"},
    {"key": "octopus", "emoji": "\U0001F419", "label": "Octopus"},
    {"key": "unicorn", "emoji": "\U0001F984", "label": "Unicorn"},
    {"key": "butterfly", "emoji": "\U0001F98B", "label": "Butterfly"},
    {"key": "penguin", "emoji": "\U0001F427", "label": "Penguin"},
    {"key": "koala", "emoji": "\U0001F428", "label": "Koala"},
    {"key": "robot", "emoji": "\U0001F916", "label": "Robot"},
    {"key": "rocket", "emoji": "\U0001F680", "label": "Rocket"},
]

LETTER_AVATAR_KEY = "letter"
DEFAULT_AVATAR = LETTER_AVATAR_KEY

_VALID_KEYS = {a["key"] for a in PRESET_AVATARS} | {LETTER_AVATAR_KEY}


def is_valid_avatar(key: str) -> bool:
    return key in _VALID_KEYS


def avatar_by_key(key: str) -> dict:
    for a in PRESET_AVATARS:
        if a["key"] == key:
            return a
    return PRESET_AVATARS[0]


def avatar_css_class(key: str) -> str:
    """CSS class for the preset's gradient background (avatar-preset-0..N
    or avatar-letter, see app/static/style.css)."""
    if key == LETTER_AVATAR_KEY:
        return "avatar-letter"
    for i, a in enumerate(PRESET_AVATARS):
        if a["key"] == key:
            return f"avatar-preset-{i}"
    return "avatar-preset-0"


def avatar_glyph(key: str, name: str) -> str:
    """What to render inside the avatar circle: the preset emoji, or the
    first letter of `name` for the letter option."""
    if key == LETTER_AVATAR_KEY:
        return (name or "?").strip()[:1].upper() or "?"
    return avatar_by_key(key)["emoji"]
