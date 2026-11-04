"""Templates and closed days sealed at rest (PR-4). The keyring is never
touched here: tests configure a vault with a fixed key and reset it."""

import datetime as dt
import os

import pytest

pytest.importorskip("cryptography")

from fidus_lab import saved_model, vault  # noqa: E402
from fidus_lab.storage import Store, sealed_path  # noqa: E402
from fidus_lab.synth import Typist  # noqa: E402
from tests.test_saved_model import _enrolled  # noqa: E402

GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
DAY = dt.date(2026, 10, 1)
KEY = bytes(range(32))


@pytest.fixture
def sealed():
    vault.configure(vault.Vault(KEY))
    yield
    vault.configure(None)


def test_a_blob_opens_only_with_its_key():
    v = vault.Vault(KEY)
    blob = v.seal(b"rhythm")
    assert vault.is_sealed(blob) and b"rhythm" not in blob
    assert v.open(blob) == b"rhythm"
    with pytest.raises(ValueError):
        vault.Vault(bytes(32)).open(blob)
    with pytest.raises(ValueError):
        v.open(blob[:-1] + bytes([blob[-1] ^ 1]))
    with pytest.raises(ValueError):
        vault.Vault(b"short")


def test_the_model_is_sealed_and_unreadable_without_the_key(tmp_path, sealed):
    e = _enrolled()
    path = tmp_path / "model.json"
    saved_model.save(path, e, {"progress": 0.6, "ready": False})
    raw = path.read_bytes()
    assert vault.is_sealed(raw) and b"progress" not in raw
    assert oct(os.stat(path).st_mode)[-3:] == "600"
    assert saved_model.load(path)[0] == e
    vault.configure(None)
    assert saved_model.load(path) is None


def test_a_plain_model_written_before_sealing_is_read_then_resealed(tmp_path):
    e = _enrolled()
    path = tmp_path / "model.json"
    saved_model.save(path, e, {"progress": 0.5})
    assert not vault.is_sealed(path.read_bytes())
    vault.configure(vault.Vault(KEY))
    try:
        assert saved_model.load(path)[0] == e
        assert vault.reseal(path) and vault.is_sealed(path.read_bytes())
        assert not vault.reseal(path)
        assert saved_model.load(path)[0] == e
    finally:
        vault.configure(None)


def test_closed_days_are_sealed_and_read_back_the_same(tmp_path, sealed):
    st = Store(tmp_path)
    st.write(Typist(seed=1, **GEN).type_segment(40, start_us=1_000), today=DAY)
    st.write(Typist(seed=2, **GEN).type_segment(40, start_us=1_000),
             today=DAY + dt.timedelta(days=1))
    st.flush()
    before, days_before = st.load_owner()
    done = st.seal_closed(today=DAY + dt.timedelta(days=1))
    plain = tmp_path / "traces" / "2026-10-01.fidustr"
    assert done == [plain] and not plain.exists() and sealed_path(plain).exists()
    # Today's file is still being appended to: it stays plain.
    assert (tmp_path / "traces" / "2026-10-02.fidustr").exists()
    assert st.days() == ["2026-10-01", "2026-10-02"]
    after, days_after = st.load_owner()
    assert [s.records for s in after] == [s.records for s in before]
    assert days_after == days_before
    # Without the key the sealed day is simply absent, never misread.
    vault.configure(None)
    assert len(st.load_owner()[0]) < len(after)


def test_sealed_guests_and_days_are_still_pruned_and_deleted(tmp_path, sealed):
    st = Store(tmp_path, retention_days=30)
    g = st.new_guest("Bob", consent=True, today=DAY)
    g.write(Typist(seed=5, **GEN).type_segment(30))
    g.close()
    st.write(Typist(seed=6, **GEN).type_segment(5), today=DAY)
    st.flush()
    st.seal_closed(today=DAY + dt.timedelta(days=1))
    assert sealed_path(tmp_path / "guests" / f"{st.guests()[0]['id']}.fidustr").exists()
    assert st.guests()[0]["bytes"] > 0 and len(st.load_guest_sessions()) == 1
    removed = st.prune(today=DAY + dt.timedelta(days=31))
    assert removed and st.guests() == [] and st.days() == []
    assert not any((tmp_path / "guests").iterdir())


def test_nothing_is_sealed_without_a_key(tmp_path):
    st = Store(tmp_path)
    st.write(Typist(seed=1, **GEN).type_segment(20), today=DAY)
    st.flush()
    assert st.seal_closed(today=DAY + dt.timedelta(days=1)) == []
    assert (tmp_path / "traces" / "2026-10-01.fidustr").exists()


def test_a_passphrase_derives_a_stable_key_salted_per_install(tmp_path):
    salt_a = vault.passphrase_salt(tmp_path)
    assert len(salt_a) == 16
    assert vault.passphrase_salt(tmp_path) == salt_a  # stable across calls
    k1 = vault.derive_key(b"correct horse", salt_a)
    assert len(k1) == 32
    assert vault.derive_key(b"correct horse", salt_a) == k1  # deterministic
    assert vault.derive_key(b"wrong horse", salt_a) != k1    # passphrase matters
    other = tmp_path / "other"
    assert vault.derive_key(b"correct horse", vault.passphrase_salt(other)) != k1  # salt matters
    with pytest.raises(ValueError):
        vault.derive_key(b"", salt_a)


def test_a_model_sealed_under_a_passphrase_opens_only_with_it(tmp_path):
    e = _enrolled()
    path = tmp_path / "model.json"
    salt = vault.passphrase_salt(tmp_path)
    vault.configure(vault.Vault(vault.derive_key(b"open sesame", salt)))
    try:
        saved_model.save(path, e, {"progress": 0.6, "ready": True})
        assert vault.is_sealed(path.read_bytes())
        assert saved_model.load(path)[0] == e
    finally:
        vault.configure(None)
    # The wrong passphrase derives a different key and cannot open the file.
    vault.configure(vault.Vault(vault.derive_key(b"wrong", salt)))
    try:
        assert saved_model.load(path) is None
    finally:
        vault.configure(None)
