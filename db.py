import os
import threading
import time

import psycopg2
from psycopg2.extras import RealDictCursor

_cache = {"data": None, "at": 0.0}
_lock = threading.Lock()
CACHE_TTL = 5.0


def _conn_kwargs(params, read_only=False):
    options = "-c search_path=petroflexx_om"
    if read_only:
        options += " -c default_transaction_read_only=on"
    return dict(
        host=params.get("DB_HOST", "ikannya-baba-db"),
        port=int(params.get("DB_PORT", 5432)),
        dbname=params.get("DB_NAME", "petroflexx_om"),
        user=params.get("DB_USER", "bi_readonly"),
        password=params.get("DB_PASSWORD", ""),
        options=options,
        cursor_factory=RealDictCursor,
    )


def get_conn(admin=False):
    """Koneksi data CMMS (mendukung override dari bi_settings) — SELALU read-only
    (default_transaction_read_only=on), jadi query data tak pernah menulis.
    Koneksi admin/bootstrap (auth & panel administrasi) memakai env ke DB aplikasi."""
    if admin:
        return psycopg2.connect(**_conn_kwargs(os.environ, read_only=False))
    return psycopg2.connect(**_conn_kwargs(_data_params(), read_only=True))


def _data_params():
    """Resolusi parameter DB untuk query data. Baca override db_* dari
    bi_settings lewat koneksi bootstrap; cache pendek per proses."""
    now = time.time()
    with _lock:
        if _cache["data"] is not None and now - _cache["at"] < CACHE_TTL:
            return _cache["data"]
    params = dict(os.environ)
    try:
        conn = psycopg2.connect(**_conn_kwargs(os.environ))
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT key, value FROM petroflexx_om.bi_settings"
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        enabled = None
        overrides = {}
        for row in rows or []:
            key, value = row["key"], row.get("value")
            if key == "db_override_enabled":
                enabled = str(value or "").strip().lower() in ("1", "true", "yes", "on")
            elif key.startswith("db_") and key != "db_override_enabled":
                overrides[key[3:].upper()] = value
        if enabled and overrides:
            for suffix in ("HOST", "PORT", "NAME", "USER", "PASSWORD"):
                val = overrides.get(suffix)
                if val:
                    params["DB_" + suffix] = str(val).strip()
    except Exception:
        pass
    with _lock:
        _cache["data"] = params
        _cache["at"] = now
    return params


def query_all(sql, params=None, admin=False):
    conn = get_conn(admin=admin)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql, params=None, admin=True):
    """Eksekusi tulis (INSERT/UPDATE/DELETE) untuk panel administrasi."""
    conn = get_conn(admin=admin)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
    finally:
        conn.close()


def allowed_categories(username):
    """Set kategori detail yang boleh dibuka user; user role admin/superadmin
    dianggap melihat semua (None). Return set kosong bila tidak ada."""
    if not username:
        return set()
    rows = query_all(
        "SELECT category FROM petroflexx_om.bi_user_detail_access "
        "WHERE bi_username = %(u)s",
        {"u": username},
        admin=True,
    )
    return {r["category"] for r in rows}