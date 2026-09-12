"""Shared "is this actually an image" content sniffer.

Used by every upload path in this app that must decide what a file really
is from its bytes, never from a client-supplied filename or Content-Type
header -- see app/services/product_photos.py and
app/services/ticket_photos.py. Contrast with
vulnerable/upload/image_processor.py and app/services/catalog_photos.py,
which deliberately trust the wrong signal.
"""

MAX_IMAGE_BYTES = 5 * 1024 * 1024

# (magic bytes, extension) -- checked in order; WebP needs a second check
# at offset 8 since RIFF is a shared container signature.
_SIGNATURES = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


def sniff_extension(data: bytes) -> str | None:
    for magic, ext in _SIGNATURES:
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None
