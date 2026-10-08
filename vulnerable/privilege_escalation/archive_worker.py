#!/usr/bin/env python3
"""Internal maintenance tool: archive processed images into cold storage.

Runs as the ops service account. Archive format handlers are pluggable so
new storage backends can be added without redeploying the worker: a
handler module is looked up by name in the shared outbox directory (where
the app writes finished exports) and imported, after its checksum has been
verified against handlers.manifest.
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

    sys.path.insert(0, OUTBOX_DIR)
    module = __import__(handler_name)

    if hasattr(module, "archive"):
        module.archive()

    print(f"archived using handler: {handler_name}")


if __name__ == "__main__":
    main()
