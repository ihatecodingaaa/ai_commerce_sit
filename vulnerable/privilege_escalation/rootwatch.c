/* rootwatch.c -- ShopLite internal admin health-check tool.
 *
 * Legacy ops utility: before a scheduled maintenance window, confirm the
 * local root/admin account credential is still the one ops expects, by
 * decrypting the stored reference credential and using it for a local
 * check. Provisioned by setup_privesc.sh; run once per lab reset/build
 * under gdb, which captures its memory into a real ELF core file at the
 * moment it crashes -- see vulnerable/privilege_escalation/README.md.
 *
 * THE BUG (intentional, for training): the credential is "protected" at
 * rest with AES-256-GCM (root_secret.enc) -- which looks like the right
 * call. But the decryption key (root_secret.key) is a plain sibling file
 * this same tool reads directly off disk -- there is no KMS, vault, or
 * hardware-backed key custody anywhere in this design. Once decrypted,
 * the plaintext credential sits in a local buffer for the rest of this
 * process's life, and nothing here ever scrubs it, the key, the nonce, or
 * the GCM tag before the process goes down (CWE-226, Sensitive
 * Information Uncleared Before Release, stacked on a CWE-320-style key-
 * management failure). "Encrypted at rest" never protected this secret
 * from anyone who can read this process's own memory after the fact --
 * and since this build keeps full debug symbols (-g, -O0, never
 * stripped), `key` and `blob` are findable by name with `gdb print`, not
 * just by raw offset (see README.md's "raise the difficulty further"
 * section for what stripping/optimizing changes).
 *
 * One thing this code DOES get right: `plaintext` -- the decrypted
 * password itself -- is cleansed immediately after use, below. That is a
 * real, correct defensive habit (OWASP / CERT C MSC06-C: clear sensitive
 * values promptly), and it closes off the laziest possible attack here --
 * a plain `strings` pass over the core dump finds no readable password.
 * What it does NOT do, and the actual point of this exercise, is clear
 * `key` or `blob` (nonce || ciphertext || tag). To whoever wrote this,
 * `plaintext` "looked like the secret" and `key`/`blob` "looked like
 * config" -- but a 32-byte AES key sitting next to the exact ciphertext
 * it opens is precisely as sensitive as the password it decrypts to, and
 * recovering it costs an attacker nothing but one AES-256-GCM decrypt call
 * on the key/blob lifted from this process's core dump. Scrubbing the
 * plaintext and stopping there is a very common, very real shape of
 * incomplete fix.
 */
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define KEY_LEN 32
#define NONCE_LEN 12
#define TAG_LEN 16
#define MAX_PLAINTEXT 256

static unsigned char *read_file(const char *path, long *out_len) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        exit(1);
    }
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);

    unsigned char *buf = malloc((size_t)len);
    if (!buf || fread(buf, 1, (size_t)len, f) != (size_t)len) {
        fprintf(stderr, "failed to read %s\n", path);
        exit(1);
    }
    fclose(f);
    *out_len = len;
    return buf;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <key-file> <enc-file>\n", argv[0]);
        return 1;
    }

    long key_len = 0, blob_len = 0;
    unsigned char *key = read_file(argv[1], &key_len);
    unsigned char *blob = read_file(argv[2], &blob_len);

    if (key_len != KEY_LEN) {
        fprintf(stderr, "bad key length: %ld\n", key_len);
        return 1;
    }
    if (blob_len < NONCE_LEN + TAG_LEN) {
        fprintf(stderr, "bad ciphertext blob\n");
        return 1;
    }

    unsigned char *nonce = blob;
    unsigned char *ciphertext = blob + NONCE_LEN;
    long ct_len = blob_len - NONCE_LEN - TAG_LEN;
    unsigned char *tag = blob + blob_len - TAG_LEN;

    unsigned char plaintext[MAX_PLAINTEXT];
    int outlen = 0, finallen = 0;

    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_DecryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, NULL, NULL);
    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_IVLEN, NONCE_LEN, NULL);
    EVP_DecryptInit_ex(ctx, NULL, NULL, key, nonce);
    EVP_DecryptUpdate(ctx, plaintext, &outlen, ciphertext, (int)ct_len);
    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, TAG_LEN, tag);
    int ok = EVP_DecryptFinal_ex(ctx, plaintext + outlen, &finallen);
    EVP_CIPHER_CTX_free(ctx);

    if (ok <= 0) {
        fprintf(stderr, "decrypt failed -- wrong key or corrupted blob\n");
        return 1;
    }
    int plaintext_len = outlen + finallen;
    (void)plaintext_len;

    fprintf(stderr, "[rootwatch] decrypted reference credential, "
                     "performing scheduled local admin check...\n");

    /* The "we handled security" line, and the actual Hop 2 bug in one
     * move: this clears the password -- the variable that LOOKS like the
     * secret -- and nothing else. `key` and `blob` are left completely
     * untouched below; they're what's still live when this crashes. */
    OPENSSL_cleanse(plaintext, sizeof(plaintext));

    fprintf(stderr, "[rootwatch] unhandled fault in admin-check comparison "
                     "routine\n");

    /* THE CRASH: deterministic, not a live race -- always the same
     * unhandled fault at the same point, right after the (incomplete)
     * cleanup above. `abort()` under `gdb generate-core-file` (see
     * setup_privesc.sh) produces a real, byte-identical ELF core every
     * time, with `key` and `blob` still live in this stack frame --
     * `plaintext` itself is gone, so recovering the password requires a
     * real AES-256-GCM decrypt, not a `strings` pass. */
    abort();
}
