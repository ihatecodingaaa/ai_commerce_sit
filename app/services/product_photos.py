"""Admin product photo storage.

This is the SECURE contrast to vulnerable/upload/image_processor.py --
worth reading side by side. Differences that matter:

  1. The file extension is chosen by THIS code, from sniffing the actual
     bytes (a handful of magic-byte checks), never from the client-supplied
     filename or Content-Type header. There is no signal here an attacker
     controls that ends up deciding how the file is later interpreted.
  2. Storage uses a randomly generated name (uuid4 + the sniffed
     extension) -- the original filename is discarded entirely, not just
     "sanitized".
  3. Nothing here ever imports, executes, or otherwise interprets the
     uploaded file as code. It is written to disk and later only ever
     read back as raw bytes by Flask's send_from_directory.
  4. It lives in its own top-level directory (PRODUCT_PHOTO_DIR), entirely
     separate from the vulnerable internal image store (UPLOAD_DIR), so
     the two pipelines can never share a path or a database row.

Route-level authorization (require_admin) is what decides WHO may call
this; this module only decides WHETHER a given upload is a real image.
"""
import os
import uuid

from app.config import config
from app.services.image_validation import MAX_IMAGE_BYTES, sniff_extension


def save_product_photo(file_storage) -> str:
    """Validate and store an uploaded product photo. Returns the stored
    filename (to save as products.image_path). Raises ValueError with a
    user-facing message if the upload is empty, too large, or not a real
    image by content.
    """
    data = file_storage.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise ValueError("uploaded file is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("photo is too large (5MB max)")

    ext = sniff_extension(data)
    if ext is None:
        raise ValueError("unsupported image format (only JPEG, PNG, GIF, or WebP are accepted)")

    os.makedirs(config.PRODUCT_PHOTO_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(config.PRODUCT_PHOTO_DIR, filename), "wb") as fh:
        fh.write(data)
    return filename


def delete_product_photo(filename: str | None):
    if not filename:
        return
    path = os.path.join(config.PRODUCT_PHOTO_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
