#!/usr/bin/env python3
"""Internal maintenance tool: archive processed images into cold storage.

Runs as `opsuser` (via the scoped sudo rule granted to `appuser` -- see
setup_privesc.sh), since archival writes to a storage path that's kept
under different, more storage-scoped permissions than the main app
account holds.

Supports a pluggable "archive format handler" -- different storage
backends occasionally need a new manifest/destination format without a
full worker redeploy, so handlers are looked up by name from a shared
drop directory (OUTBOX_DIR, where the main app writes finished exports)
and imported dynamically by name.

THE BUG (intentional, for training): CWE-427, Uncontrolled Search Path
Element. OUTBOX_DIR is inserted at the *front* of sys.path before the
handler module is imported by name -- and that directory is writable by
`appuser` (the account invoking this script via sudo), not just by
`opsuser`. Whoever can write a same-named .py file into OUTBOX_DIR before
this script runs controls exactly what code gets imported, and that
import's top-level code runs as whichever account actually performs it.

A prior security review flagged the raw dynamic import below and asked
for "some integrity check" on handler modules. `_verify_handler()` below
is that fix, and it's broken in a specific, realistic way (CWE-354,
Improper Validation of Integrity Check Value): the recorded checksum a
handler must match lives in `handlers.manifest`, in the *same*
appuser-writable OUTBOX_DIR as the handler modules themselves. The check
proves a handler wasn't swapped out after being registered -- it proves
nothing about whether the account that registered it was allowed to.
`appuser` can compute and write its own correct checksum for its own
planted module just as easily as it writes the module.
"""
import hashlib
import json
import sys

OUTBOX_DIR = "/opt/shop/backups/outbox"
MANIFEST_PATH = f"{OUTBOX_DIR}/handlers.manifest"


def _verify_handler(handler_name):
    handler_path = f"{OUTBOX_DIR}/{handler_name}.py"

    try:
        with open(handler_path, "rb") as f:
            source = f.read()
    except OSError:
        print(f"no such handler module: {handler_name}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError):
        print("handlers.manifest missing or unreadable -- refusing to load "
              "an unregistered handler", file=sys.stderr)
        sys.exit(1)

    expected = manifest.get(handler_name)
    if not expected:
        print(f"handler {handler_name!r} is not registered in "
              f"handlers.manifest", file=sys.stderr)
        sys.exit(1)

    actual = hashlib.sha256(source).hexdigest()
    if actual != expected:
        print(f"handler {handler_name!r} failed its integrity check "
              f"(expected {expected}, got {actual})", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) != 2:
        print("usage: archive_worker.py <handler-name>", file=sys.stderr)
        sys.exit(1)

    handler_name = sys.argv[1]
    _verify_handler(handler_name)

    sys.path.insert(0, OUTBOX_DIR)  # <-- arbitrary code execution: whoever
    module = __import__(handler_name)  # controls OUTBOX_DIR controls this import

    if hasattr(module, "archive"):
        module.archive()

    print(f"archived using handler: {handler_name}")


if __name__ == "__main__":
    main()
