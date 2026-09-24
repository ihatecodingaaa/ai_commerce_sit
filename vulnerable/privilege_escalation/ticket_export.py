#!/usr/bin/env python3
"""Internal maintenance tool: re-hydrate a previously cached ticket-export
object (written by the nightly backup job) instead of re-querying the full
ticket history from scratch every run. Runs as `opsuser`, invoked via the
scoped sudo rule granted to `appuser` (see setup_privesc.sh) -- never as
root, and appuser cannot run anything else as opsuser.

THE BUG (intentional, for training): CWE-502, Deserialization of Untrusted
Data. `pickle.load()` will execute arbitrary code embedded in the input
file via any object's `__reduce__`/`__reduce_ex__` method -- pickle is not
a safe format for data whose origin isn't fully trusted, and this tool
trusts whatever path it's handed with no validation at all. Whoever can
invoke this tool with a file they control gets code execution as whichever
account runs it.
"""
import pickle
import sys


def main():
    if len(sys.argv) != 2:
        print("usage: ticket_export.py <cache-file>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "rb") as fh:
        cached = pickle.load(fh)  # <-- arbitrary code execution, as this process's user

    print(f"Loaded cached export: {cached!r}")


if __name__ == "__main__":
    main()
