#!/usr/bin/env python3
"""Generates Hop 2's AES-256-GCM-encrypted root credential blob.

Run once per `setup_privesc.sh` invocation (image build, and every
`reset_lab.sh`) -- a fresh random password and a fresh random AES key
every time, exactly like every other generated secret in this lab (see
SECURITY.md: "never hardcoded"). There is no fixed/shared value a student
could look up once and reuse across resets.

Writes:
  <key_path>  -- raw 32-byte AES-256 key, root-owned, mode 600
  <enc_path>  -- nonce(12) || ciphertext || tag(16), root-owned, mode 600

Prints the plaintext password (and nothing else) to stdout so
setup_privesc.sh can capture it and set it as root's *actual* account
password via chpasswd -- it is not stored anywhere else in plaintext.
This is the same value `rootwatch` (vulnerable/privilege_escalation/
rootwatch.c) decrypts at startup, which is Hop 2's target.
"""
import os
import secrets
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_LEN = 12


def main():
    if len(sys.argv) != 3:
        print("usage: gen_root_secret.py <key-out-path> <enc-out-path>", file=sys.stderr)
        sys.exit(1)

    key_path, enc_path = sys.argv[1], sys.argv[2]

    password = "Root-" + secrets.token_urlsafe(18)
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(NONCE_LEN)

    # cryptography's AESGCM.encrypt() returns ciphertext with the 16-byte
    # tag already appended -- matches what rootwatch.c expects to find
    # after the leading nonce.
    ciphertext_and_tag = AESGCM(key).encrypt(nonce, password.encode("utf-8"), None)

    with open(key_path, "wb") as f:
        f.write(key)
    with open(enc_path, "wb") as f:
        f.write(nonce + ciphertext_and_tag)

    print(password)


if __name__ == "__main__":
    main()
