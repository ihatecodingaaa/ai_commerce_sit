"""Preset profile-photo library.

Deliberately a fixed, server-defined set -- not a file upload. A customer
picks a `key` from this list; nothing is ever written to disk on their
behalf. This keeps the account-editing feature from becoming a second
file-upload attack surface alongside the two that already exist on
purpose/by-design (vulnerable/upload/ and app/services/product_photos.py).
Rendering is a monochrome line icon (app/templates/_icons.html, matching
the storefront's icon language) inside a plain circle -- no image assets
at all, so there's nothing to store, serve, or validate as a file.

Preset `key`s are the stable, stored identifier (seed data and existing
accounts reference these) -- only the icon/label shown for each key has
changed from the original animal-emoji picker to something that fits the
storefront's quiet-luxury aesthetic.

LETTER_AVATAR_KEY is the classic "first letter of your name on a colored
circle" look (what every user had before presets existed) -- kept as an
explicit, selectable option rather than removed, since plenty of people
just want their initial.
"""

PRESET_AVATARS = [
    {"key": "fox", "icon": "leaf", "label": "Leaf"},
    {"key": "panda", "icon": "feather", "label": "Feather"},
    {"key": "owl", "icon": "moon", "label": "Moon"},
    {"key": "octopus", "icon": "star", "label": "Star"},
    {"key": "unicorn", "icon": "flame", "label": "Flame"},
    {"key": "butterfly", "icon": "droplet", "label": "Droplet"},
    {"key": "penguin", "icon": "mountain", "label": "Mountain"},
    {"key": "koala", "icon": "compass", "label": "Compass"},
    {"key": "robot", "icon": "sun", "label": "Sun"},
    {"key": "rocket", "icon": "gem", "label": "Gem"},
]

LETTER_AVATAR_KEY = "letter"

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


def avatar_icon_name(key: str) -> str:
    """The _icons.html icon name for a preset avatar key (used by the
    avatar_content Jinja macro; irrelevant for the letter avatar)."""
    return avatar_by_key(key)["icon"]
