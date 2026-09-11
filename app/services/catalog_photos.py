"""Product-photo handling for the catalog-sync integration
(app/routes/api_catalog.py) -- the path the warehouse/inventory system
uses to push a new product (including its photo) directly, with no human
admin involved. This predates the hardened admin-upload path
(app/services/product_photos.py: magic-byte sniffing, randomized
filenames, never executed) and was never brought up to the same
standard, because it "only" requires a service credential -- exactly the
kind of gap that shows up in real orgs when a security fix lands on the
path people actually look at, but not every other path reachable with
the same end result.

*** DELIBERATE VULNERABILITY (CWE-434: Unrestricted Upload of File with
Dangerous Type) -- this lab's actual entry point, see
docs/attack-timeline.md Stage 6-9. ***

looks_like_jpeg_filename() only checks whether ".jpg" appears anywhere in
the client-supplied filename -- not that it's the real (final) extension,
and not the actual file content. A file named `plugin.jpg.py` satisfies
this check (the substring is present), while its REAL extension -- the
one vulnerable/upload/image_processor.py actually branches on once the
file reaches app/routes/api_images.py via
app/services/image_client.py::upload_screenshot_bytes -- is `.py`.
"""
import os
import uuid

from app.config import config
from app.services.image_client import upload_screenshot_bytes


def looks_like_jpeg_filename(filename: str) -> bool:
    """The deliberate gap: a substring check, not a suffix check."""
    return ".jpg" in filename.lower()


def sync_product_photo(file_storage) -> str | None:
    """Forward an uploaded product photo through the shared internal image
    service -- this is where the deliberate vulnerability actually fires,
    since that service decides what to do based on the real filename
    extension (see module docstring). Also stores a copy under
    PRODUCT_PHOTO_DIR, under a random name, so the product photo displays
    on the storefront the same way an admin-uploaded one would. Returns
    the stored filename, or None if the internal service rejected it.
    """
    data = file_storage.read()
    image_id = upload_screenshot_bytes(data, file_storage.filename, file_storage.mimetype)
    if image_id is None:
        return None

    os.makedirs(config.PRODUCT_PHOTO_DIR, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.jpg"
    with open(os.path.join(config.PRODUCT_PHOTO_DIR, stored_name), "wb") as fh:
        fh.write(data)
    return stored_name
