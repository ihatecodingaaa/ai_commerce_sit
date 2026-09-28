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
"""
import sys

OUTBOX_DIR = "/opt/shop/backups/outbox"


def main():
    if len(sys.argv) != 2:
        print("usage: archive_worker.py <handler-name>", file=sys.stderr)
        sys.exit(1)

    handler_name = sys.argv[1]
    sys.path.insert(0, OUTBOX_DIR)  # <-- arbitrary code execution: whoever
    module = __import__(handler_name)  # controls OUTBOX_DIR controls this import

    if hasattr(module, "archive"):
        module.archive()

    print(f"archived using handler: {handler_name}")


if __name__ == "__main__":
    main()
