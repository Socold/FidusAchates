"""Templates and traces sealed at rest (PR-4), with the key in the keyring.

What the daemon keeps is enough to forge me: the template holds the means and
spreads of my rhythm, and a day of reduced trace holds every hold and gap it
was fitted from (research/articles/2026-11-04-stolen-rhythm.md). This module
seals both with AES-256-GCM. The key is 32 random bytes generated once and
stored in the session keyring through libsecret; it never touches the disk in
clear.

A sealed file starts with `MAGIC`, then a 12-byte nonce, then the ciphertext
and its tag. Reading accepts plain files too, so data written before sealing
existed stays readable and is sealed the next time it is written.

What this protects: copies of the data folder that leave the session (a
backup, a sync, a disk image, another account). What it does not: a process
running as me while the session is open can ask the keyring for the key, as
the daemon does. /home is already encrypted at the block level on my machine;
sealing adds the copies that the disk encryption does not follow.

`configure` is called once by the daemon. Without it (tests, offline tools,
a session without a keyring) nothing is sealed and reading a sealed file
fails with ValueError.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

MAGIC = b"FIDV\x01"
_NONCE = 12
_AAD = b"fidusachates"
SCHEMA = "org.fidusachates.Vault"
_LABEL = "FidusAchates template and trace key"


class Vault:
    def __init__(self, key: bytes) -> None:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # optional dependency

        if len(key) != 32:
            raise ValueError("the vault key is 32 bytes")
        self._aead = AESGCM(key)

    def seal(self, plain: bytes) -> bytes:
        nonce = os.urandom(_NONCE)
        return MAGIC + nonce + self._aead.encrypt(nonce, plain, _AAD)

    def open(self, blob: bytes) -> bytes:
        from cryptography.exceptions import InvalidTag

        if not is_sealed(blob):
            raise ValueError("not a sealed blob")
        nonce = blob[len(MAGIC):len(MAGIC) + _NONCE]
        try:
            return self._aead.decrypt(nonce, blob[len(MAGIC) + _NONCE:], _AAD)
        except InvalidTag as e:
            raise ValueError("sealed blob does not open with this key") from e


_active: Vault | None = None


def configure(vault: Vault | None) -> None:
    global _active
    _active = vault


def active() -> Vault | None:
    return _active


def is_sealed(blob: bytes) -> bool:
    return blob[:len(MAGIC)] == MAGIC


def read_bytes(path: Path) -> bytes:
    """A file's content, opened if sealed. ValueError if it is sealed and no
    vault (or another key) is configured."""
    data = path.read_bytes()
    if not is_sealed(data):
        return data
    if _active is None:
        raise ValueError(f"{path.name} is sealed and no key is available")
    return _active.open(data)


def write_bytes(path: Path, plain: bytes) -> None:
    """Write atomically, mode 0600, sealed when a vault is configured."""
    data = _active.seal(plain) if _active is not None else plain
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def reseal(path: Path) -> bool:
    """Seal a file written in clear before sealing existed, in place."""
    if _active is None or not path.exists():
        return False
    data = path.read_bytes()
    if is_sealed(data):
        return False
    write_bytes(path, data)
    return True


def passphrase_salt(root: Path) -> bytes:
    """A stable 16-byte salt kept next to the data, for a passphrase-derived
    key. Not secret: it only stops the same passphrase deriving the same key on
    two installs. Created 0600 on first use."""
    p = root / "vault.salt"
    try:
        data = p.read_bytes()
        if len(data) == 16:
            return data
    except OSError:
        pass
    salt = os.urandom(16)
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(salt)
    return salt


def derive_key(passphrase: bytes, salt: bytes) -> bytes:
    """A 32-byte vault key from a passphrase, with scrypt (standard library, no
    dependency). Used only when there is no keyring to hold a random key: a
    headless session can still seal its templates behind a passphrase. Sized
    for one unlock at daemon start (about 32 MiB, a fraction of a second)."""
    if not passphrase:
        raise ValueError("the passphrase is empty")
    return hashlib.scrypt(passphrase, salt=salt, n=2 ** 15, r=8, p=1,
                          maxmem=64 * 1024 * 1024, dklen=32)


def keyring_key(create: bool = True) -> bytes | None:
    """The vault key from the session keyring, created on first use. None
    when there is no keyring to ask (no session bus, locked keyring, no
    libsecret), in which case the daemon writes in clear and says so."""
    try:
        import gi

        gi.require_version("Secret", "1")
        from gi.repository import Secret

        schema = Secret.Schema.new(SCHEMA, Secret.SchemaFlags.NONE,
                                   {"purpose": Secret.SchemaAttributeType.STRING})
        attrs = {"purpose": "templates-and-traces"}
        hexkey = Secret.password_lookup_sync(schema, attrs, None)
        if hexkey:
            key = bytes.fromhex(hexkey)
            return key if len(key) == 32 else None
        if not create:
            return None
        key = os.urandom(32)
        if not Secret.password_store_sync(schema, attrs, Secret.COLLECTION_DEFAULT,
                                          _LABEL, key.hex(), None):
            return None
        return key
    except Exception:  # no gi, no bus, locked or absent keyring: all mean "no key"
        return None
