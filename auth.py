import hashlib
import hmac
import os
import sys

ITERATIONS = 200000
ALGO = "sha256"


def hash_password(password, salt=None, iterations=ITERATIONS):
    salt = salt or os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac(ALGO, password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return "pbkdf2:{}:{}${}${}".format(ALGO, iterations, salt, dk.hex())


def verify_password(password, stored):
    if not stored:
        return False
    try:
        meta, salt, _ = stored.strip().split("$")
        _, algo, iterations = meta.split(":")
        if algo != ALGO:
            return False
        iterations = int(iterations)
        salt.encode("ascii")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt=salt, iterations=iterations), stored.strip())


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "hash":
        print(hash_password(sys.argv[2]))
    elif len(sys.argv) >= 4 and sys.argv[1] == "verify":
        print("OK" if verify_password(sys.argv[2], sys.argv[3]) else "FAIL")
    else:
        print("usage: python3 auth.py hash <password> | verify <password> <hash>")
        sys.exit(1)