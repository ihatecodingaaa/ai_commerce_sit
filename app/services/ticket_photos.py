"""Customer support-ticket photo attachments.

Same secure pattern as app/services/product_photos.py: real content
sniffed from bytes (never the client-supplied filename or Content-Type),
a randomly generated server-side filename, and its own top-level
directory, read back only as raw bytes.

Deliberately does NOT go through app/services/image_client.py /
app/routes/api_images.py: that internal API's own processing step
(vulnerable/upload/image_processor.py) imports and executes any upload
whose real extension is .py, regardless of which caller submitted it --
see that module's docstring. Nothing a customer can reach should ever be
routed through it, so this feature has its own, independent, boring
storage path instead.
"""
import os
import uuid

from app.config import config
from app.services.image_validation import MAX_IMAGE_BYTES, sniff_extension


def save_ticket_photo(file_storage) -> str:
    """Validate and store a customer's ticket photo. Returns the stored
    filename (to save as tickets.customer_photo_path). Raises ValueError
    with a user-facing message if the upload is empty, too large, or not
    a real image by content.
    """
    data = file_storage.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise ValueError("uploaded file is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("photo is too large (5MB max)")

    ext = sniff_extension(data)
    if ext is None:
        raise ValueError("unsupported image format (only JPEG, PNG, GIF, or WebP are accepted)")

    os.makedirs(config.TICKET_PHOTO_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(config.TICKET_PHOTO_DIR, filename), "wb") as fh:
        fh.write(data)
    return filename


def delete_ticket_photo(filename: str | None):
    if not filename:
        return
    path = os.path.join(config.TICKET_PHOTO_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
