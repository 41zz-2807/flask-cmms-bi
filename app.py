import base64
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from io import StringIO

import pandas as pd
from playwright.sync_api import sync_playwright

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from auth import verify_password
from db import allowed_categories, category_overrides, dashboard_title, query_all
from queries import (
    ASSET_WO_SQL,
    COMPARE_RAW_SQL,
    COMPARE_REFS_SQL,
    DATA_QUALITY_RAW_SQL,
    KPI_SITE_RAW_SQL,
    MTBF_MTTR_RAW_SQL,
    PARETO_RAW_SQL,
PROFIL_TEKNISI_BASE_SQL,
    PROFIL_TEKNISI_EVENT_SQL,
    QUERIES,
    SPAREPART_WO_SQL,
    SUMMARY_SQL,
    TABLE_SQL,
    TECHNISI_BACKLOG_SQL,
    TREN_BULANAN_RAW_SQL,
    WO_APPROVALS_SQL,
    WO_LIST_SQL,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

DASHBOARD_TITLE = os.getenv("DASHBOARD_TITLE", "Aplikasi CMMS - Petroflexx OM")
APP_VERSION = os.getenv("APP_VERSION", "1.3.0")
LICENSE_TEXT = os.getenv("LICENSE_TEXT", "Powered By Smart-Plus.id 2026")
APP_VERSION_FULL = "v{}.{}".format(APP_VERSION, date.today().strftime("%y%m%d"))
FOLDER_COLORS = ["#1985a0", "#e67e22", "#27ae60", "#8e44ad", "#c0392b"]


def get_dashboard_title():
    """Judul dashboard: override dari bi_settings bila ada, else env default."""
    return dashboard_title() or DASHBOARD_TITLE
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "").strip()
if not MEDIA_ROOT:
    media_wo = os.getenv("MEDIA_WO_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "media", "WO")).rstrip("/")
    MEDIA_ROOT = os.path.dirname(media_wo) if os.path.basename(media_wo) == "WO" else media_wo

LOGIN_SQL = """
    SELECT username, password_hash, COALESCE(full_name, '') AS full_name,
           COALESCE(role, 'user') AS role
    FROM bi_user
    WHERE username = %(username)s AND is_active = true;
"""

ADMIN_ROLES = ("superadmin",)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _tg_notify(username, ok, extra=""):
    """Kirim notifikasi login ke Telegram (fire-and-forget).
    Token/chat dari env; jika kosong otomatis di-skip. Tidak pernah melempar."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    status = "BERHASIL" if ok else "GAGAL"
    ip = (request.headers.get("X-Forwarded-For", "") or request.remote_addr or "-").split(",")[0].strip()
    text = (
        "Login CMMS BI {}\n"
        "User: {}\n"
        "IP: {}\n"
        "Waktu: {}{}"
    ).format(status, username or "(tanpa user)", ip,
             datetime.now().strftime("%d/%m/%Y %H:%M:%S"), extra)

    def _send():
        try:
            payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
            req = urllib.request.Request(
                "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN),
                data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=8) as resp:
                print("TELNOTIF: login {} untuk '{}' terkirim (http {}).".format(
                    "BERHASIL" if ok else "GAGAL", username, resp.status))
        except Exception as e:
            print("TELNOTIF: kirim gagal untuk '{}': {}".format(username, e))

    threading.Thread(target=_send, daemon=True).start()

DOCS_SQL = """
    SELECT document_id AS wo_id, file_name, folder_file, content_type
    FROM om_upload_file
    WHERE active = 'Y' AND source = 'WO' AND document_id = ANY(%(ids)s)
    ORDER BY om_upload_file_id;
"""

DOC_FILE_SQL = """
    SELECT file_name, folder_file
    FROM om_upload_file
    WHERE active = 'Y' AND source = 'WO' AND document_id = %(wo_id)s AND file_name = %(file_name)s
    LIMIT 1;
"""


def media_path():
    abspath = os.path.abspath(MEDIA_ROOT)
    return abspath if os.path.isdir(abspath) else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user"):
            return view(*args, **kwargs)
        if request.path.startswith("/api/") or request.path.startswith("/doc/"):
            return jsonify({"error": "login diperlukan"}), 401
        return redirect(url_for("login", next=request.path + ("?" + request.query_string.decode() if request.query_string else "")))
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET" and session.get("user"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            error = "Username dan password wajib diisi."
            _tg_notify(username, False)
        else:
            rows = query_all(LOGIN_SQL, {"username": username}, admin=True)
            user = rows[0] if rows else None
            if user and verify_password(password, user["password_hash"]):
                session["user"] = username
                session["full_name"] = user["full_name"] or username
                session["role"] = user["role"] or "user"
                _tg_notify(username, True, "\nRole: {}".format(user["role"] or "user"))
                next_url = request.form.get("next") or request.args.get("next")
                if not next_url:
                    if user["role"] == "superadmin":
                        next_url = url_for("admin.dashboard")
                    else:
                        next_url = url_for("index")
                if not next_url.startswith("/"):
                    next_url = url_for("index")
                return redirect(next_url)
            error = "Username atau password salah."
            _tg_notify(username, False)
    return render_template("login.html", title=get_dashboard_title(), error=error, today=date.today().isoformat(), next=request.args.get("next"))


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.context_processor
def inject_user():
    username = session.get("user", "")
    role = session.get("role", "user")
    return {
        "current_user": username,
        "current_full_name": session.get("full_name", username),
        "app_version": APP_VERSION_FULL,
        "license_text": LICENSE_TEXT,
        "dashboard_title": get_dashboard_title(),
        "user_role": role,
        "is_admin": role in ADMIN_ROLES,
    }


def can_view(category):
    """Kategori detail boleh dibuka oleh user saat ini."""
    role = session.get("role", "user")
    if role in ADMIN_ROLES:
        return True
    return category in allowed_categories(session.get("user", ""))


def can_compare():
    """Fitur Perbandingan Dinamis boleh dibuka user saat ini."""
    role = session.get("role", "user")
    if role in ADMIN_ROLES:
        return True
    return "compare" in allowed_categories(session.get("user", ""))


@app.route("/api/docs")
@login_required
def api_docs():
    ids = [int(x) for x in request.args.get("ids", "").split(",") if x.strip().isdigit()]
    out = {}
    if not ids:
        return jsonify({"docs": out})
    rows = query_all(DOCS_SQL, {"ids": ids})
    base = media_path()
    for r in rows:
        rel = os.path.normpath(os.path.join(r["folder_file"] or "", r["file_name"] or ""))
        full = os.path.join(base, rel) if base else ""
        url = "/doc/{}/{}".format(r["wo_id"], urllib.parse.quote(r["file_name"] or ""))
        entry = {
            "name": r["file_name"],
            "type": r["content_type"],
            "url": url,
            "ok": bool(base and full and os.path.isfile(full) and full.startswith(base + os.sep)),
        }
        out.setdefault(str(r["wo_id"]), []).append(entry)
    return jsonify({"docs": out})


@app.route("/doc/<int:wo_id>/<path:filename>")
@login_required
def doc_file(wo_id, filename):
    name = os.path.basename(filename)
    if not name:
        abort(404)
    rows = query_all(DOC_FILE_SQL, {"wo_id": wo_id, "file_name": name})
    if not rows:
        abort(404)
    base = media_path()
    if not base:
        abort(404)
    folder = rows[0]["folder_file"] or ""
    if os.path.normpath(os.path.join(base, folder, name)).startswith(base + os.sep):
        return send_from_directory(base, os.path.join(folder, name), conditional=True)
    abort(404)


@app.route("/")
@login_required
def index():
    groups = [
        ("Ringkasan & KPI", ["kpi_site", "tren_bulanan", "biaya_wo", "wo_request", "wo_durasi_proses"]),
        ("Pemeliharaan & Keandalan", ["asset_wo_summary", "pm_compliance", "mtbf_mttr", "asset_wo_frequency"]),
        ("Sparepart & Material", ["pareto_sparepart", "sparepart_fast_moving"]),
        ("Sumber Daya & Teknisi", ["profil_teknisi", "technician_performance"]),
        ("Kesehatan Data", ["data_quality"]),
    ]
    cards = []
    color_i = 0
    role = session.get("role", "user")
    allowed = None if role in ADMIN_ROLES else allowed_categories(session.get("user", ""))
    overrides = category_overrides()
    for group, keys in groups:
        items = []
        for k in keys:
            cfg = QUERIES.get(k)
            if not cfg:
                continue
            if allowed is not None and k not in allowed:
                continue
            ov = overrides.get(k) or {}
            items.append({
                "key": k,
                "title": (ov.get("title") or cfg["title"]),
                "color": (ov.get("color") or FOLDER_COLORS[color_i % len(FOLDER_COLORS)]),
            })
            color_i += 1
        if items:
            cards.append({"title": group, "cards": items})
    return render_template(
        "dashboard.html",
        title=get_dashboard_title(),
        today=date.today().isoformat(),
        groups=cards,
        hidden_cards=(allowed is not None and not cards and "compare" not in allowed),
        can_compare=allowed is None or "compare" in allowed,
    )


def parse_filters():
    today = date.today()
    end = request.args.get("to", today.isoformat())
    start = request.args.get("from", (today - timedelta(days=30)).isoformat())
    m_org_ids = None
    sites = request.args.get("sites", "")
    if sites:
        try:
            ids = [int(s) for s in sites.split(",") if s.strip()]
            if ids:
                m_org_ids = ids
        except ValueError:
            pass
    return {"start_date": start, "end_date": end, "m_org_ids": m_org_ids}


OPEN_STATES = ("CO", "RE", "IP", "DR")


def _num(value, nd=1):
    if value is None or pd.isna(value):
        return None
    return round(float(value), nd)


def _f(value):
    try:
        return "{:,.0f}".format(float(value)).replace(",", ".")
    except (TypeError, ValueError):
        return "-"


_print_lock = threading.Lock()


def _json_default(o):
    if isinstance(o, datetime):
        return o.strftime("%Y-%m-%d %H:%M")
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError("Object of type %s is not JSON serializable" % type(o).__name__)


def generate_pdf(html, wait_ms=600):
    with _print_lock:
        pw = sync_playwright().start()
        browser = None
        try:
            browser = pw.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            page = browser.new_page(
                viewport={"width": 1120, "height": 1500},
                device_scale_factor=2,
                color_scheme="light",
            )
            try:
                page.set_content(
                    html,
                    wait_until="networkidle",
                    timeout=60000,
                )
                page.wait_for_timeout(wait_ms)
                pdf = page.pdf(format="A4", print_background=True)
            finally:
                page.close()
        finally:
            if browser is not None:
                browser.close()
            pw.stop()
        return pdf


def compute_kpi_site(raw_rows):
    if not raw_rows:
        return [], None
    df = pd.DataFrame(raw_rows)
    df["budget_f"] = pd.to_numeric(df["budget"], errors="coerce").fillna(0.0)
    closed = df["status"].eq("CL")
    is_sch = df["tipe"].astype(str).str.upper().eq("SCH")
    open_ = df["status"].isin(OPEN_STATES)
    key = ["site_id", "site_name"]

    total = df.groupby(key, sort=False).size()
    sch = df.loc[is_sch].groupby(key, sort=False).size()
    req = df.loc[~is_sch].groupby(key, sort=False).size()
    op = df.loc[open_].groupby(key, sort=False).size()
    cl = df.loc[closed].groupby(key, sort=False).size()
    sch_cl = df.loc[closed & is_sch].groupby(key, sort=False).size()
    biaya = df.groupby(key, sort=False)["budget_f"].sum()
    biaya_cl = df.loc[closed].groupby(key, sort=False)["budget_f"].sum()
    avg = df.groupby(key, sort=False)["budget_f"].mean()

    def g(series, k):
        return int(series.get(k, 0))

    rows = []
    for site_id, site_name in total.index:
        k = (site_id, site_name)
        t = int(total[k])
        s = g(sch, k)
        r = g(req, k)
        c = g(cl, k)
        sc = g(sch_cl, k)
        rows.append({
            "site": site_name,
            "total_wo": t,
            "sch": s,
            "req": r,
            "open": g(op, k),
            "pct_closed": round(c / t * 100, 1) if t else 0.0,
            "pct_pm": round(sc / s * 100, 1) if s else 0.0,
            "budget": float(biaya[k]),
            "budget_closed": float(biaya_cl.get(k, 0.0)),
            "avg_budget": float(avg[k]),
        })
    rows.sort(key=lambda x: x["total_wo"], reverse=True)

    tot_wo = int(df.shape[0])
    tot_sch = int(is_sch.sum())
    tot_closed = int(closed.sum())
    tot_sch_cl = int((closed & is_sch).sum())
    tot_budget = float(df["budget_f"].sum())
    tot_budget_cl = float(df.loc[closed, "budget_f"].sum())
    tot_open = int(open_.sum())
    rows.append({
        "site": "Semua Site",
        "total_wo": tot_wo,
        "sch": tot_sch,
        "req": tot_wo - tot_sch,
        "open": tot_open,
        "pct_closed": round(tot_closed / tot_wo * 100, 1) if tot_wo else 0.0,
        "pct_pm": round(tot_sch_cl / tot_sch * 100, 1) if tot_sch else 0.0,
        "budget": tot_budget,
        "budget_closed": tot_budget_cl,
        "avg_budget": tot_budget / tot_wo if tot_wo else 0.0,
    })
    summary = {
        "total_wo": tot_wo,
        "tot_sch": tot_sch,
        "tot_req": tot_wo - tot_sch,
        "tot_open": tot_open,
        "pct_closed": round(tot_closed / tot_wo * 100, 1) if tot_wo else 0.0,
        "budget": tot_budget,
        "tot_budget_closed": tot_budget_cl,
        "sites": len(total),
    }
    return rows, summary


def compute_trend(raw_rows, start_date, end_date):
    if not raw_rows:
        return [], [], None
    df = pd.DataFrame(raw_rows)
    df["created"] = pd.to_datetime(df["created"], errors="coerce")
    df["budget_f"] = pd.to_numeric(df["budget"], errors="coerce").fillna(0.0)
    df["bulan"] = df["created"].dt.to_period("M")
    is_sch = df["tipe"].astype(str).str.upper().eq("SCH")

    pivot = df.groupby("bulan").agg(
        total=("bulan", "size"),
        sch=("tipe", lambda s: s.astype(str).str.upper().eq("SCH").sum()),
        biaya=("budget_f", "sum"),
    )
    pivot["req"] = pivot["total"] - pivot["sch"]
    idx = pd.period_range(start_date[:7], end_date[:7], freq="M")
    pivot = pivot.reindex(idx, fill_value=0)

    total = pivot["total"]
    pivot["ma3"] = total.rolling(3, min_periods=1).mean()
    pivot["mom"] = (total.pct_change() * 100).replace([float("inf"), float("-inf")], float("nan"))
    pivot["yoy"] = (total.pct_change(periods=12) * 100).replace([float("inf"), float("-inf")], float("nan"))
    month_avg = pivot.groupby(pivot.index.month)["total"].mean()
    base = total.mean() or 1
    pivot["seasonal"] = pivot.index.month.map(month_avg) / base

    n = len(total)
    if n > 1:
        x = pd.Series(range(n), dtype="float")
        slope = x.cov(total.astype(float)) / x.var()
    else:
        slope = 0.0
    trend_dir = "Naik" if slope > 0.15 else ("Turun" if slope < -0.15 else "Stabil")

    chart = []
    rows = []
    peak = None
    for per, rlt in pivot.iterrows():
        label = str(per)
        chart.append({"x": label, "total": int(rlt["total"]), "sch": int(rlt["sch"]), "req": int(rlt["req"])})
        if peak is None or rlt["total"] > peak[1]:
            peak = (label, int(rlt["total"]))
        rows.append({
            "bulan": label,
            "total": int(rlt["total"]),
            "sch": int(rlt["sch"]),
            "req": int(rlt["req"]),
            "biaya": float(rlt["biaya"]),
            "mom_total": round(rlt["mom"], 1) if pd.notna(rlt["mom"]) else None,
            "yoy_total": round(rlt["yoy"], 1) if pd.notna(rlt["yoy"]) else None,
            "ma3_total": round(rlt["ma3"], 1),
            "seasonal": round(rlt["seasonal"], 2),
        })
    summary = {
        "total_wo": int(total.sum()),
        "avg_month": round(float(total.mean()), 1),
        "peak_label": peak[0] if peak else "-",
        "trend_dir": trend_dir,
        "biaya": float(pivot["biaya"].sum()),
    }
    return chart, rows, summary


def compute_pareto(raw_rows, top_chart=25, limit=300):
    if not raw_rows:
        return [], [], None
    df = pd.DataFrame(raw_rows)
    df["qty_f"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0.0)
    g = df.groupby("sparepart")["qty_f"].sum().sort_values(ascending=False)
    g = g[g > 0]
    total = g.sum()
    if not total:
        return [], [], None
    cum = g.cumsum()
    share = g / total * 100
    cum_pct = cum / total * 100

    def cls(v):
        return "A" if v <= 80 else ("B" if v <= 95 else "C")

    klas = pd.Series([cls(v) for v in cum_pct], index=g.index)
    cnt = klas.value_counts().to_dict()
    share_by = share.groupby(klas).sum().to_dict()

    rows = [
        {
            "sparepart": name,
            "qty": float(g[name]),
            "share": round(float(share[name]), 2),
            "cum": round(float(cum_pct[name]), 2),
            "klas": cls(cum_pct[name]),
        }
        for name in g.index
    ]
    chart = [
        {"x": name, "y": float(g[name]), "cum": round(float(cum_pct[name]), 2)}
        for name in g.index[:top_chart]
    ]
    summary = {
        "tot_items": int(len(g)),
        "total_qty": float(total),
        "cnt_a": int(cnt.get("A", 0)),
        "cnt_b": int(cnt.get("B", 0)),
        "cnt_c": int(cnt.get("C", 0)),
        "share_a": round(float(share_by.get("A", 0.0)), 1),
        "share_b": round(float(share_by.get("B", 0.0)), 1),
        "share_c": round(float(share_by.get("C", 0.0)), 1),
    }
    return chart, rows[:limit], summary


def compute_mtbf_mttr(raw_rows, top_chart=10, limit=300):
    if not raw_rows:
        return [], [], None
    df = pd.DataFrame(raw_rows)
    df["created"] = pd.to_datetime(df["created"], errors="coerce")
    df["closed"] = pd.to_datetime(df["closed"], errors="coerce")
    d = df.sort_values(["aset", "created"]).copy()
    d["gap"] = d.groupby("aset")["created"].diff().dt.total_seconds() / 86400.0
    d["dur"] = (d["closed"] - d["created"]).dt.total_seconds() / 86400.0

    events = d.groupby("aset").size()
    mtbf = d.groupby("aset")["gap"].mean()
    mttr = d.loc[d["closed"].notna()].groupby("aset")["dur"].mean()

    chart = [
        {
            "x": a,
            "mttr": _num(mttr[a]) if a in mttr.index else None,
            "mtbf": _num(mtbf[a]) if a in mtbf.index else None,
        }
        for a in events.sort_values(ascending=False).index[:top_chart]
    ]
    rows = []
    for rank, a in enumerate(events.sort_values(ascending=False).index[:limit], 1):
        sub = d[d["aset"] == a]
        rows.append({
            "aset": a,
            "wo_total": int(events[a]),
            "mttr": _num(mttr[a]) if a in mttr.index else None,
            "mtbf": _num(mtbf[a]) if a in mtbf.index else None,
            "last_date": sub["created"].iloc[-1].strftime("%Y-%m-%d") if pd.notna(sub["created"].iloc[-1]) else None,
            "status_terakhir": sub["status"].iloc[-1] or None,
        })
    summary = {
        "tot_aset": int(len(events)),
        "tot_wo": int(events.sum()),
        "avg_mttr": _num(mttr.mean()),
        "avg_mtbf": _num(mtbf.mean()),
    }
    return chart, rows, summary


def compute_data_quality(raw_rows, limit=500):
    if not raw_rows:
        return [], [], None
    df = pd.DataFrame(raw_rows)
    df["created"] = pd.to_datetime(df["created"], errors="coerce")
    df["closed"] = pd.to_datetime(df["closed"], errors="coerce")
    now = pd.Timestamp.now()
    issues = []

    add = issues.append
    for r in df.itertuples(index=False):
        if pd.isna(r.asset_id):
            add({"kategori": "Tanpa Aset", "no_wo": r.no_wo or "-",
                 "tanggal": r.created.strftime("%Y-%m-%d") if pd.notna(r.created) else None,
                 "status": r.status or "-", "detail": "WO tidak terkait aset"})
        if r.tipe == "REQ" and (pd.isna(r.classification) or r.classification == 0):
            add({"kategori": "Tanpa Klasifikasi", "no_wo": r.no_wo or "-",
                 "tanggal": r.created.strftime("%Y-%m-%d") if pd.notna(r.created) else None,
                 "status": r.status or "-", "detail": "classifications REQ kosong"})
        if pd.notna(r.closed) and pd.notna(r.created) and r.closed < r.created:
            add({"kategori": "Tanggal Tidak Masuk Akal", "no_wo": r.no_wo or "-",
                 "tanggal": r.created.strftime("%Y-%m-%d") if pd.notna(r.created) else None,
                 "status": r.status or "-", "detail": "closed_date sebelum created_date"})
        if r.status == "CL" and pd.isna(r.closed):
            add({"kategori": "Konsistensi Status", "no_wo": r.no_wo or "-",
                 "tanggal": r.created.strftime("%Y-%m-%d") if pd.notna(r.created) else None,
                 "status": r.status or "-", "detail": "CL tanpa closed_date"})
        if pd.notna(r.created) and r.created > now:
            add({"kategori": "Tanggal Futuristik", "no_wo": r.no_wo or "-",
                 "tanggal": r.created.strftime("%Y-%m-%d") if pd.notna(r.created) else None,
                 "status": r.status or "-", "detail": "created_date di masa depan"})

    dup = df[df.duplicated("no_wo", keep=False)]
    dup_counts = dup.groupby("no_wo").size()
    for no_wo, n in dup_counts.items():
        add({"kategori": "Duplikat", "no_wo": no_wo, "tanggal": None,
             "status": "-", "detail": "No WO muncul {}x".format(int(n))})

    rows = issues[:limit]
    chart = []
    for k in ["Tanpa Aset", "Tanpa Klasifikasi", "Tanggal Tidak Masuk Akal",
              "Konsistensi Status", "Tanggal Futuristik", "Duplikat"]:
        c = sum(1 for i in issues if i["kategori"] == k)
        chart.append({"x": k, "y": c})

    tot = int(df.shape[0])
    req = df[df["tipe"] == "REQ"]
    tot_req = int(req.shape[0])
    pct_aset = round(int(df["asset_id"].notna().sum()) / tot * 100, 1) if tot else 0.0
    pct_klas = round(int(req["classification"].notna().gt(0).sum()) / tot_req * 100, 1) if tot_req else 0.0
    summary = {
        "tot_wo": tot,
        "pct_aset": pct_aset,
        "pct_klas": pct_klas,
        "tot_isu": len(issues),
        "tot_dup": int(len(dup_counts)),
        "tot_ase": int(df["asset_id"].isna().sum()),
        "tot_klas": int(req["classification"].isna().sum() + (req["classification"] == 0).sum()),
    }
    return chart, rows, summary


def compute_teknisi(base_rows, event_rows, backlog_rows, top_chart=6, limit=50):
    if not base_rows:
        return [], [], None
    df = pd.DataFrame(base_rows)
    df["created"] = pd.to_datetime(df["created"], errors="coerce")
    df["start_ts"] = pd.to_datetime(df["start_ts"], errors="coerce")
    df["cl_ts"] = pd.to_datetime(df["cl_ts"], errors="coerce")
    if event_rows:
        ev = pd.DataFrame(event_rows)
        ev["ts"] = pd.to_datetime(ev["ts"], errors="coerce")
        last = ev.loc[ev.groupby("wo_id")["ts"].idxmax(), ["wo_id", "teknisi"]]
        df = df.merge(last, on="wo_id", how="left")
    df["teknisi"] = df["teknisi"].fillna("Tanpa Teknisi")
    df["bulan"] = df["created"].dt.to_period("M").astype(str)
    df["dur"] = (df["cl_ts"] - df["start_ts"]).dt.total_seconds() / 86400.0
    df.loc[df["status"] != "CL", "dur"] = float("nan")

    total = df.groupby("teknisi").size().sort_values(ascending=False)
    closed = df["status"].eq("CL")
    wo_cl = df.loc[closed].groupby("teknisi").size()
    dur_grp = df.loc[closed].groupby("teknisi")["dur"]
    med = dur_grp.median().fillna(float("nan"))
    p95 = dur_grp.quantile(0.95)

    backlog_map = {}
    if backlog_rows:
        bl = pd.DataFrame(backlog_rows)
        open_stats = ("CO", "RE", "IP", "DR")
        bl = bl[bl["status"].isin(open_stats)]
        for tk, n in bl.groupby("teknisi").size().items():
            backlog_map[tk] = int(n)

    rows = []
    for tk in total.index[:limit]:
        rows.append({
            "teknisi": tk,
            "wo_total": int(total[tk]),
            "wo_cl": int(wo_cl.get(tk, 0)),
            "med_hari": _num(med.get(tk)) if tk in med.index else None,
            "p95_hari": _num(p95.get(tk)) if tk in p95.index else None,
            "backlog": int(backlog_map.get(tk, 0)),
        })

    wlm = df.groupby(["teknisi", "bulan"]).size()
    top = total.index[:top_chart]
    months = sorted(df["bulan"].dropna().unique())
    chart = []
    for m in months:
        r = {"bulan": m}
        for tk in top:
            r[tk] = int(wlm.get((tk, m), 0))
        chart.append(r)

    dur_all = df.loc[closed, "dur"].dropna()
    summary = {
        "tot_teknisi": int(len(total)),
        "tot_wo": int(df.shape[0]),
        "med_global": _num(dur_all.median()) if len(dur_all) else None,
        "p95_global": _num(dur_all.quantile(0.95)) if len(dur_all) else None,
        "tot_backlog": int(sum(backlog_map.values())),
    }
    return chart, rows, summary


def build_cards(category, summary):
    if not summary:
        return None
    if category == "asset_wo_frequency":
        return [
            {"v": summary["tot_aset"], "l": "Aset (Top-10)", "accent": True},
            {"v": summary["tot_wo"], "l": "Total WO", "accent": True},
            {"v": summary["top_cnt"], "l": "WO Terbanyak/Aset", "accent": True},
            {"v": round(summary["tot_wo"] / summary["tot_aset"], 1) if summary["tot_aset"] else 0, "l": "Rata-rata WO/Aset"},
        ]
    if category == "pm_compliance":
        return [
            {"v": summary["total"], "l": "Jadwal PM (SCH)", "accent": True},
            {"v": summary["pct"], "l": "% Sesuai Jadwal", "suffix": "%"},
            {"v": summary["tepat"], "l": "Tepat Jadwal"},
            {"v": summary["awal"], "l": "Dikerjakan Lebih Awal"},
            {"v": summary["telat"], "l": "Terlambat", "accent": True},
            {"v": summary["belum"], "l": "Belum Dikerjakan", "accent": True},
        ]
    if category == "sparepart_fast_moving":
        return [
            {"v": summary["tot_items"], "l": "Sparepart (Top-10)", "accent": True},
            {"v": summary["tot_qty"], "l": "Total Pemakaian (Qty)", "accent": True},
            {"v": summary["tot_wo"], "l": "Total WO", "accent": True},
            {"v": round(summary["tot_qty"] / summary["tot_items"], 1) if summary["tot_items"] else 0, "l": "Rata-rata Qty/Item"},
        ]
    if category == "technician_performance":
        return [
            {"v": summary["tot_teknisi"], "l": "Teknisi (Top-10)", "accent": True},
            {"v": summary["tot_wo"], "l": "Total WO", "accent": True},
            {"v": summary["top_cnt"], "l": "WO Terbanyak/Teknisi", "accent": True},
            {"v": summary["avg_cnt"], "l": "Rata-rata WO/Teknisi"},
        ]
    if category == "pareto_sparepart":
        return [
            {"v": summary["tot_items"], "l": "Total Item", "accent": True},
            {"v": summary["total_qty"], "l": "Total Pemakaian (Qty)", "accent": True},
            {"v": summary["cnt_a"], "l": "Item Kelas A", "t": "Kontribusi {}% qty".format(summary["share_a"]), "accent": True},
            {"v": summary["cnt_b"], "l": "Item Kelas B", "t": "Kontribusi {}% qty".format(summary["share_b"]), "accent": True},
            {"v": summary["cnt_c"], "l": "Item Kelas C", "t": "Kontribusi {}% qty".format(summary["share_c"]), "accent": True},
        ]
    if category == "mtbf_mttr":
        return [
            {"v": summary["tot_aset"], "l": "Total Aset", "accent": True},
            {"v": summary["tot_wo"], "l": "Total Event (WO SCH)", "accent": True},
            {"v": summary["avg_mttr"], "l": "MTTR Rata-rata (hari)", "suffix": " hari"},
            {"v": summary["avg_mtbf"], "l": "MTBF Rata-rata (hari)", "suffix": " hari"},
        ]
    if category == "profil_teknisi":
        return [
            {"v": summary["tot_teknisi"], "l": "Total Teknisi", "accent": True},
            {"v": summary["tot_wo"], "l": "Total WO Diproses", "accent": True},
            {"v": summary["med_global"], "l": "Median Durasi (hari)", "suffix": " hari"},
            {"v": summary["p95_global"], "l": "P95 Durasi (hari)", "suffix": " hari"},
            {"v": summary["tot_backlog"], "l": "Total Backlog (WO)", "accent": True},
        ]
    if category == "data_quality":
        return [
            {"v": summary["tot_wo"], "l": "Total WO Dicek", "accent": True},
            {"v": summary["pct_aset"], "l": "Aset Terisi (%)", "suffix": "%"},
            {"v": summary["pct_klas"], "l": "Klasifikasi Terisi (%)", "suffix": "%"},
            {"v": summary["tot_isu"], "l": "Total Isu", "accent": True},
            {"v": summary["tot_dup"], "l": "No WO Duplikat", "accent": True},
        ]
    if category == "asset_wo_summary":
        return [
            {"v": summary.get("sch"), "l": "WO SCH", "accent": True},
            {"v": summary.get("req"), "l": "WO REQ", "accent": True},
            {"v": summary.get("mec"), "l": "MEC", "t": "MECANICAL"},
            {"v": summary.get("ine"), "l": "INE", "t": "INSTRUMENT / ELECTRICAL"},
            {"v": summary.get("sip"), "l": "SIP", "t": "SIPIL"},
            {"v": summary.get("gen"), "l": "GEN", "t": "GENERAL"},
        ]
    if category == "wo_request":
        return [
            {"v": summary.get("total"), "l": "Total Request", "accent": True},
            {"v": summary.get("closed"), "l": "Selesai (CL)", "accent": True},
            {"v": summary.get("open"), "l": "Belum Selesai", "accent": True},
            {"v": summary.get("rejected"), "l": "Di-Reject (RE)", "accent": True},
        ]
    if category == "wo_durasi_proses":
        return [
            {"v": summary.get("total"), "l": "WO Selesai (CL)", "accent": True},
            {"v": summary.get("avg_total_hari"), "l": "Rata-rata Total", "suffix": " hari"},
            {"v": summary.get("med_total_hari"), "l": "Median Total", "suffix": " hari"},
            {"v": summary.get("avg_approval_hari"), "l": "Rata-rata Approval", "suffix": " hari"},
            {"v": summary.get("avg_exec_hari"), "l": "Eksekusi → Close", "suffix": " hari"},
            {"v": summary.get("pct_dalam_7hari"), "l": "Selesai ≤ 7 Hari", "suffix": "%"},
        ]
    if category == "kpi_site":
        return [
            {"v": summary["total_wo"], "l": "Total WO", "accent": True},
            {"v": summary["tot_sch"], "l": "WO SCH", "accent": True},
            {"v": summary["tot_req"], "l": "WO REQ", "accent": True},
            {"v": summary["tot_open"], "l": "WO Open", "accent": True},
            {"v": summary["pct_closed"], "l": "% Closed", "suffix": "%"},
            {"v": summary["budget"], "l": "Biaya Semua (Rp)", "money": True},
            {"v": summary["tot_budget_closed"], "l": "Biaya Closed (Rp)", "money": True},
        ]
    if category == "tren_bulanan":
        return [
            {"v": summary["total_wo"], "l": "Total WO", "accent": True},
            {"v": summary["avg_month"], "l": "Rata-rata WO/bulan", "accent": True},
            {"v": summary["peak_label"], "l": "Bulan Puncak", "accent": True},
            {"v": summary["trend_dir"], "l": "Arah Tren"},
            {"v": summary["biaya"], "l": "Biaya Total (Rp)", "money": True},
        ]
    return None


@app.route("/api/sites")
@login_required
def api_sites():
    sql = """
        SELECT o.m_org_id AS site_id, o.name AS site_name, COUNT(wo.om_wo_id) AS total_wo
        FROM m_org o
        LEFT JOIN om_wo wo ON wo.m_org_id = o.m_org_id
        GROUP BY o.m_org_id, o.name
        ORDER BY total_wo DESC;
    """
    return jsonify({"sites": query_all(sql)})


@app.route("/api/sparepart-wo")
@login_required
def api_sparepart_wo():
    params = parse_filters()
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"rows": []})
    params["name"] = name
    return jsonify({"rows": query_all(SPAREPART_WO_SQL, params)})


@app.route("/api/asset-wo")
@login_required
def api_asset_wo():
    params = parse_filters()
    name = request.args.get("name", "").strip()
    tipe = request.args.get("tipe", "").strip().upper()
    if not name or tipe not in ("SCH", "REQ"):
        return jsonify({"rows": []})
    params["name"] = name
    params["tipe"] = tipe
    return jsonify({"rows": query_all(ASSET_WO_SQL, params)})


@app.route("/api/wo-list")
@login_required
def api_wo_list():
    params = parse_filters()
    tipe = request.args.get("tipe", "").strip().upper()
    params["tipe"] = tipe if tipe in ("SCH", "REQ") else None
    params["aset"] = request.args.get("aset", "").strip() or None
    params["site"] = request.args.get("site", "").strip() or None
    params["bulan"] = request.args.get("bulan", "").strip()[:7] or None
    params["teknisi"] = request.args.get("teknisi", "").strip() or None
    status = request.args.get("status", "").strip().lower()
    params["status"] = status if status in ("open", "closed", "backlog") else None
    if not (params["aset"] or params["site"] or params["bulan"] or params["teknisi"]):
        return jsonify({"rows": []})
    return jsonify({"rows": query_all(WO_LIST_SQL, params)})


@app.route("/api/wo-approvals")
@login_required
def api_wo_approvals():
    try:
        wo_id = int(request.args.get("wo_id", ""))
    except (TypeError, ValueError):
        return jsonify({"error": "wo_id tidak valid"}), 400
    rows = query_all(WO_APPROVALS_SQL, {"wo_id": wo_id})
    return jsonify({"wo_id": wo_id, "rows": rows})


@app.route("/api/export/<category>")
@login_required
def api_export(category):
    if category not in QUERIES:
        return jsonify({"error": "kategori tidak ditemukan"}), 404
    if not can_view(category):
        return jsonify({"error": "akses ke kategori ini ditolak"}), 403
    params = parse_filters()
    rows = query_all(TABLE_SQL[category], params)
    norm = [{k: (float(v) if isinstance(v, Decimal) else v) for k, v in r.items()} for r in rows]
    df = pd.DataFrame(norm)
    buf = StringIO()
    df.to_csv(buf, index=False, sep=";")
    filename = "{} {}-{}.csv".format(category, params["start_date"], params["end_date"])
    resp = Response("\ufeff" + buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename*=UTF-8''{}".format(urllib.parse.quote(filename))
    return resp


@app.route("/api/charts")
@login_required
def api_charts():
    params = parse_filters()
    overrides = category_overrides()
    out = {}
    for key, cfg in QUERIES.items():
        if cfg["type"] == "none":
            continue
        out[key] = {
            "title": (overrides.get(key) or {}).get("title") or cfg["title"],
            "type": cfg["type"],
            "data": query_all(cfg["sql"], params),
        }
    return jsonify(out)


@app.route("/detail/<category>")
@login_required
def detail(category):
    if category not in QUERIES:
        return jsonify({"error": "kategori tidak ditemukan"}), 404
    if not can_view(category):
        abort(403)
    ov = (category_overrides().get(category) or {})
    chart_title = ov.get("title") or QUERIES[category]["title"]
    return render_template(
        "detail.html",
        category=category,
        chart_title=chart_title,
        dashboard_title=get_dashboard_title(),
        today=date.today().isoformat(),
        can_compare=can_compare(),
    )


@app.route("/api/detail/<category>")
@login_required
def api_detail(category):
    if category not in QUERIES:
        return jsonify({"error": "kategori tidak ditemukan"}), 404
    if not can_view(category):
        return jsonify({"error": "akses ke kategori ini ditolak"}), 403
    params = parse_filters()
    try:
        limit = min(int(request.args.get("limit", 500)), 5000)
    except ValueError:
        limit = 500
    chart_type, chart, table, summary = build_detail_data(category, params, limit)
    return jsonify({
        "category": category,
        "title": QUERIES[category]["title"],
        "chart_type": chart_type,
        "chart": chart,
        "table": table,
        "summary": summary,
        "row_limit": limit,
    })


def build_detail_data(category, params, limit=500):
    chart_type = QUERIES[category]["type"]
    summary = None
    if category == "kpi_site":
        chart = query_all(QUERIES[category]["sql"], params)
        raw = query_all(KPI_SITE_RAW_SQL, params)
        table, ksum = compute_kpi_site(raw)
        summary = ksum
        cards = build_cards(category, summary)
        summary = {**(summary or {}), "cards": cards}
    elif category == "tren_bulanan":
        raw = query_all(TREN_BULANAN_RAW_SQL, params)
        chart, table, tsum = compute_trend(raw, params["start_date"], params["end_date"])
        summary = tsum
        cards = build_cards(category, summary)
        summary = {**(summary or {}), "cards": cards}
    elif category == "pareto_sparepart":
        raw = query_all(PARETO_RAW_SQL, params)
        chart, table, psum = compute_pareto(raw)
        summary = psum
        cards = build_cards(category, summary)
        summary = {**(summary or {}), "cards": cards}
    elif category == "mtbf_mttr":
        raw = query_all(MTBF_MTTR_RAW_SQL, params)
        chart, table, msum = compute_mtbf_mttr(raw)
        summary = msum
        cards = build_cards(category, summary)
        summary = {**(summary or {}), "cards": cards}
    elif category == "profil_teknisi":
        base = query_all(PROFIL_TEKNISI_BASE_SQL, params)
        ev = query_all(PROFIL_TEKNISI_EVENT_SQL, params)
        bk = query_all(TECHNISI_BACKLOG_SQL, {})
        chart, table, tsum = compute_teknisi(base, ev, bk)
        summary = tsum
        cards = build_cards(category, summary)
        summary = {**(summary or {}), "cards": cards}
    elif category == "data_quality":
        raw = query_all(DATA_QUALITY_RAW_SQL, params)
        chart, table, dsum = compute_data_quality(raw)
        summary = dsum
        cards = build_cards(category, summary)
        summary = {**(summary or {}), "cards": cards}
    else:
        chart = [] if chart_type == "none" else query_all(QUERIES[category]["sql"], params)
        table_sql = TABLE_SQL[category] + f" LIMIT {limit}"
        table = query_all(table_sql, params)
        if category in SUMMARY_SQL:
            srows = query_all(SUMMARY_SQL[category], params)
            raw = srows[0] if srows else None
            if raw:
                raw = {k: (float(v) if isinstance(v, Decimal) else v) for k, v in raw.items()}
            cards = build_cards(category, raw)
            summary = {**(raw or {}), "cards": cards} if cards else None
    return chart_type, chart, table, summary


def build_recommendations(category, summary, table):
    recs = []
    s = summary or {}
    table = table or []

    def add(level, text):
        recs.append({"level": level, "text": text})

    if not s:
        return recs

    per_site = [r for r in table if isinstance(r, dict) and r.get("site") and r.get("site") != "Semua Site"]
    if category == "kpi_site":
        add("info", "Periode ini tercatat {} WO pada {} site dengan {}% berstatus CL.".format(
            _f(s.get("total_wo")), _f(s.get("sites")), s.get("pct_closed")))
        if s.get("tot_open"):
            add("tinggi", "Masih ada {} WO terbuka (CO/RE/IP/DR). Direkomendasikan melakukan prioritisasi dan tindak lanjut penutupan terhadap WO terbuka tertua.".format(_f(s["tot_open"])))
        pcl = sum(r.get("pct_closed", 0) for r in per_site) / len(per_site) if per_site else 0
        if per_site and pcl < 70:
            add("tinggi", "Rata-rata penyelesaian WO per site {}% di bawah target 70%. Evaluasi kapasitas tim dalam menutup WO.".format(round(pcl, 1)))
        worst = min(per_site, key=lambda r: r.get("pct_pm", 100)) if per_site else None
        if worst and worst.get("pct_pm", 100) < 80:
            add("sedang", "Kepatuhan PM terendah di {} ({}%). Perketat pelaksanaan jadwal rutin di site tersebut.".format(worst["site"], worst.get("pct_pm")))
        if s.get("budget"):
            closed_frac = (s.get("tot_budget_closed") or 0) / s["budget"] * 100
            add("info", "Anggaran periode ini Rp {}; {}% terserap pada WO yang sudah CL.".format(
                _f(s["budget"]), round(closed_frac, 1)))
    elif category == "tren_bulanan":
        peak_total = next((r.get("total") for r in table if isinstance(r, dict) and r.get("bulan") == s.get("peak_label")), None)
        add("info", "Total WO periode {} dengan rata-rata {} per bulan; puncak pada {} ({} WO).".format(
            _f(s.get("total_wo")), _f(s.get("avg_month")), s.get("peak_label"), _f(peak_total)))
        if s.get("trend_dir") == "Naik":
            add("tinggi", "Tren WO cenderung NAIK. Antisipasi dengan penajaman jadwal PM dan kesiapan kapasitas/personel sebelum beban bertambah.")
        elif s.get("trend_dir") == "Turun":
            add("info", "Tren WO cenderung TURUN — sinyal positif; pertahankan & dokumentasikan praktik yang mendukung.")
        else:
            add("info", "Tren WO relatif stabil pada periode ini.") 
    elif category == "pareto_sparepart":
        add("info", "{} jenis sparepart dipakai total {} unit. Kelas A ({} item) menyumbang {}% pemakaian, kelas B ({} item) {}%, kelas C ({} item) {}%.".format(
            _f(s.get("tot_items")), _f(s.get("total_qty")),
            _f(s.get("cnt_a")), s.get("share_a"), _f(s.get("cnt_b")), s.get("share_b"),
            _f(s.get("cnt_c")), s.get("share_c")))
        top_a = [r for r in table if r.get("klas") == "A"][:3]
        if top_a:
            add("tinggi", "Fokus stok & pengamanan sparepart kelas A: {}.".format(
                ", ".join("{} ({} unit)".format(r["sparepart"], _f(r["qty"])) for r in top_a)))
    elif category == "mtbf_mttr":
        add("info", "MTBF rata-rata {} hari dan MTTR rata-rata {} hari pada {} aset di periode berjalan.".format(
            s.get("avg_mtbf"), s.get("avg_mttr"), _f(s.get("tot_aset"))))
        low = [r for r in table if r.get("mtbf") is not None and r.get("mtbf") <= 7][:3]
        if low:
            add("tinggi", "Aset dengan MTBF rendah (potensi keandalan buruk): {} — direkomendasikan Root Cause Analysis (RCA).".format(
                ", ".join("{} ({} WO)".format(r["aset"], _f(r["wo_total"])) for r in low)))
        slow = [r for r in table if r.get("mttr") is not None and r.get("mttr") > 60][:3]
        if slow:
            add("sedang", "MTTR tinggi pada {} — periksa ketersediaan sparepart, tooling, dan prosedur perbaikan.".format(
                ", ".join(r["aset"] for r in slow)))
    elif category == "profil_teknisi":
        add("info", "{} teknisi aktif dengan {} WO diproses; durasi penyelesaian median {} hari dan P95 {} hari.".format(
            _f(s.get("tot_teknisi")), _f(s.get("tot_wo")), s.get("med_global"), s.get("p95_global")))
        if s.get("tot_backlog"):
            add("tinggi", "Total backlog {} WO terbuka di tangan teknisi. Tinjau pembagian beban kerja agar backlog tidak terakumulasi.".format(_f(s["tot_backlog"])))
        high = max((r for r in table if isinstance(r, dict) and r.get("backlog")), key=lambda r: r.get("backlog", 0), default=None)
        if high and high.get("backlog"):
            add("sedang", "Backlog terbesar pada {} ({} WO terbuka). Prioritaskan alokasi bantuan/review tugas.".format(
                high.get("teknisi"), _f(high.get("backlog"))))
    elif category == "data_quality":
        add("info", "Data periode inventaris: {} WO; kepemilikan aset terisi {}%, klasifikasi REQ terisi {}%.".format(
            _f(s.get("tot_wo")), s.get("pct_aset"), s.get("pct_klas")))
        if s.get("tot_isu"):
            add("tinggi", "Terdeteksi {} isu kualitas data ({} WO tanpa aset, {} tanpa klasifikasi, {} duplikat). Direkomendasikan perbaikan input sebelum analisis lanjutan.".format(
                _f(s["tot_isu"]), _f(s.get("tot_ase")), _f(s.get("tot_klas")), _f(s.get("tot_dup"))))
    elif category == "asset_wo_frequency":
        add("info", "{} aset masuk 10 besar dengan {} WO; aset dengan WO terbanyak memicu {} WO.".format(
            _f(s.get("tot_aset")), _f(s.get("tot_wo")), _f(s.get("top_cnt"))))
        if (s.get("top_cnt") or 0) > 10:
            add("tinggi", "Frekuensi WO tinggi pada aset teratas — direkomendasikan RCA dan penyesuaian strategi pemeliharaan (PM/failure-driven).")
    elif category == "pm_compliance":
        pct = s.get("pct") or 0
        add("info", "Dari {} WO terjadwal (berdasarkan jadwal pelaksanaan), {}% mulai dikerjakan pada atau sebelum jadwal ({} tepat, {} lebih awal); {} terlambat; {} belum dikerjakan.".format(
            _f(s.get("total")), pct, _f(s.get("tepat")), _f(s.get("awal")), _f(s.get("telat")), _f(s.get("belum"))))
        if pct < 80:
            add("tinggi", "Kepatuhan terhadap jadwal {}% — di bawah target 80%. Susun rencana catch-up, pastikan WO yang terlambat/belum dikerjakan segera ditindaklanjuti.".format(pct))
        elif (s.get("telat") or 0) > 0:
            add("sedang", "Ada {} WO yang mulai dikerjakan setelah tanggal jadwal — analisis hambatan agar pelaksanaan berikutnya tepat waktu.".format(_f(s.get("telat"))))
    elif category == "sparepart_fast_moving":
        add("info", "{} item fast-moving terpakai {} unit dalam {} WO pada periode berjalan.".format(
            _f(s.get("tot_items")), _f(s.get("tot_qty")), _f(s.get("tot_wo"))))
        if s.get("tot_items"):
            add("sedang", "Pastikan kebijakan min-max stock dan kontrak pengadaan mengikuti laju pemakaian sparepart fast-moving.")
    elif category == "technician_performance":
        add("info", "{} teknisi menangani {} WO; alokasi ke teknisi teratas {} WO (rata-rata {} WO/teknisi).".format(
            _f(s.get("tot_teknisi")), _f(s.get("tot_wo")), _f(s.get("top_cnt")), _f(s.get("avg_cnt"))))
        if (s.get("top_cnt") or 0) > (s.get("avg_cnt") or 0) * 1.5:
            add("sedang", "Distribusi beban tidak merata (teknisi teratas {} vs rata-rata {}). Imbangi distribusi tugas untuk keseimbangan workload.".format(
                _f(s.get("top_cnt")), _f(s.get("avg_cnt"))))
    elif category == "biaya_wo":
        add("info", "Menampilkan WO dengan biaya (budget) tertinggi pada periode berjalan untuk evaluasi pengeluaran.")
        if s.get("total") or s.get("budget"):
            add("sedang", "Review setiap WO berbiaya tertinggi: validasi cakupan kerja sebelum membebankan anggaran serupa.")
    elif category == "asset_wo_summary":
        total_sch = s.get("sch") or 0
        total_req = s.get("req") or 0
        add("info", "Rekap: {} WO SCH vs {} WO REQ pada periode ini.".format(_f(total_sch), _f(total_req)))
        if total_req and total_req > total_sch:
            add("sedang", "Proporsi WO REQ lebih besar dari SCH — korelasikan dengan age assets, evaluasi program PM.")
        if s.get("mec"):
            add("info", "Klasifikasi REQ: {} mekanikal, {} instrument, {} sipil, {} general.".format(
                _f(s.get("mec")), _f(s.get("ine")), _f(s.get("sip")), _f(s.get("gen"))))
    elif category == "wo_request":
        add("info", "Periode ini tercatat {} request (nomor WO ber-REQ); {} sudah selesai, {} belum selesai, {} di-reject.".format(
            _f(s.get("total")), _f(s.get("closed")), _f(s.get("open")), _f(s.get("rejected"))))
        if s.get("rejected"):
            add("tinggi", "{} request berstatus RE (tidak sesuai). Periksa alasan reject pada kolom deskripsi dan ajukan ulang bila perlu.".format(_f(s["rejected"])))
        if s.get("total") and s.get("closed") and s.get("closed") / s["total"] < 0.5:
            add("sedang", "Kurang dari setengah request telah selesai — tinjau prioritas penyelesaian request.")
    elif category == "wo_durasi_proses":
        add("info", "{} WO selesai pada periode ini; rata-rata proses {} hari (median {} hari), P90 {} hari. {}% WO tuntas dalam 7 hari.".format(
            _f(s.get("total")), s.get("avg_total_hari"), s.get("med_total_hari"),
            s.get("p90_total_hari"), s.get("pct_dalam_7hari")))
        if s.get("pct_dalam_7hari") is not None and s["pct_dalam_7hari"] < 60:
            add("tinggi", "Hanya {}% WO selesai dalam 7 hari. Percepat tahap approval dan penutupan untuk mengurangi bottleneck proses.".format(s["pct_dalam_7hari"]))
        elif s.get("avg_total_hari") is not None and s["avg_total_hari"] > 10:
            add("tinggi", "Durasi rata-rata {} hari — lambat. Identifikasi WO dengan durasi approval/klerikal terpanjang pada tabel di bawah untuk evaluasi SLA masing-masing tahap.".format(s["avg_total_hari"]))
        if s.get("avg_exec_hari") is not None and s["avg_exec_hari"] > 3:
            add("sedang", "Waktu rata-rata dari selesai eksekusi (CO) hingga close (CL) {} hari — periksa keterlambatan administrasi penutupan WO.".format(s["avg_exec_hari"]))
        if s.get("avg_approval_hari") is not None and s["avg_approval_hari"] > 5:
            add("sedang", "Waktu rata-rata approval & eksekusi {} hari. Tinjau SLA approver tiap level agar approval tidak menjadi antrean terpanjang.".format(s["avg_approval_hari"]))
    return recs


@app.route("/api/report/<category>")
@login_required
def api_report(category):
    if category not in QUERIES:
        return jsonify({"error": "kategori tidak ditemukan"}), 404
    if not can_view(category):
        return jsonify({"error": "akses ke kategori ini ditolak"}), 403
    params = parse_filters()
    chart_type, chart, table, summary = build_detail_data(category, params, limit=100)
    recs = build_recommendations(category, summary, table)
    cards = (summary or {}).get("cards") or []

    def card_disp(c):
        v = c.get("v")
        if c.get("money") and v is not None:
            return "Rp " + _f(v)
        if v is None:
            return "-"
        if c.get("suffix"):
            return ("{:,.1f}".format(v)).replace(",", ".") + c["suffix"]
        if isinstance(v, (int, float)):
            return _f(v)
        return str(v)

    cards = [dict(c, disp=card_disp(c)) for c in cards]

    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    with open(os.path.join(static_dir, "echarts.min.js"), encoding="utf-8") as f:
        echarts_js = f.read()
    with open(os.path.join(static_dir, "chart.js"), encoding="utf-8") as f:
        chart_js = f.read()
    try:
        with open(os.path.join(static_dir, "logo-petroflexx.png"), "rb") as f:
            logo_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        logo_uri = None

    html = render_template(
        "report.html",
        dashboard_title=get_dashboard_title(),
        category_title=(category_overrides().get(category) or {}).get("title") or QUERIES[category]["title"],
        category=category,
        from_date=params["start_date"],
        to_date=params["end_date"],
        chart_type=chart_type,
        has_chart=chart_type != "none" and bool(chart),
        chart_json=json.dumps(chart, ensure_ascii=False, default=_json_default),
        table_json=json.dumps(table[:60], ensure_ascii=False, default=_json_default),
        cards=cards,
        recommendations=recs,
        echarts_js=echarts_js,
        chart_js=chart_js,
        logo_uri=logo_uri,
        generated_by=session.get("full_name") or session.get("user", ""),
        generated_at=date.today().isoformat(),
    )
    try:
        pdf = generate_pdf(html)
    except Exception as exc:
        app.logger.exception("gagal generate pdf %s", category)
        return jsonify({"error": "gagal generate PDF: %s" % exc}), 500
    filename = "laporan-{}-{}-{}.pdf".format(category, params["start_date"], params["end_date"])
    resp = Response(pdf, mimetype="application/pdf")
    resp.headers["Content-Disposition"] = "attachment; filename*=UTF-8''{}".format(urllib.parse.quote(filename))
    return resp


COMPARE_METRICS = [
    {"key": "total_wo", "label": "Total WO", "kind": "int"},
    {"key": "sch", "label": "WO SCH", "kind": "int"},
    {"key": "req", "label": "WO REQ", "kind": "int"},
    {"key": "open", "label": "WO Open", "kind": "int"},
    {"key": "closed", "label": "WO Closed", "kind": "int"},
    {"key": "pct_closed", "label": "% Closed", "kind": "pct"},
    {"key": "budget", "label": "Biaya Total (Rp)", "kind": "money"},
    {"key": "avg_budget", "label": "Rata-rata/WO (Rp)", "kind": "money"},
    {"key": "backlog", "label": "Backlog (WO)", "kind": "int"},
]


def _compute_group_metrics(rows, metrics):
    n = len(rows)
    if n == 0:
        return {m["key"]: (0.0 if m["kind"] == "pct" else 0) for m in metrics}
    df = pd.DataFrame(rows)
    tipe = df["tipe"].astype(str).str.upper()
    status = df["status"].astype(str)
    budget = pd.to_numeric(df["budget"], errors="coerce").fillna(0.0)
    closed = int(status.eq("CL").sum())
    out = {}
    for m in metrics:
        k = m["key"]
        if k == "total_wo":
            out[k] = n
        elif k == "sch":
            out[k] = int(tipe.eq("SCH").sum())
        elif k == "req":
            out[k] = int(tipe.eq("REQ").sum())
        elif k == "open":
            out[k] = int(status.isin(OPEN_STATES).sum())
        elif k == "closed":
            out[k] = closed
        elif k == "pct_closed":
            out[k] = _num(100.0 * closed / n)
        elif k == "budget":
            out[k] = _num(float(budget.sum()), 0)
        elif k == "avg_budget":
            out[k] = _num(float(budget.sum()) / n, 0)
        elif k == "backlog":
            out[k] = int(status.isin(OPEN_STATES).sum())
        else:
            out[k] = 0
    return out


def build_compare(data):
    groups_raw = data.get("groups") or []
    metric_keys = [str(m) for m in (data.get("metrics") or [])]
    base = data.get("base")
    if not isinstance(groups_raw, list) or len(groups_raw) < 2:
        raise ValueError("Perbandingan membutuhkan minimal 2 grup")
    metrics = [m for m in COMPARE_METRICS if m["key"] in metric_keys] or COMPARE_METRICS[:3]
    groups = []
    allowed_types = ("", "all", "SCH", "REQ")
    for g in groups_raw[:10]:
        label = str(g.get("label") or "").strip() or "Grup {}".format(len(groups) + 1)
        site_ids = None
        try:
            ids = [int(s) for s in (g.get("sites") or []) if str(s).strip().isdigit()]
            if ids:
                site_ids = ids
        except (TypeError, ValueError):
            pass
        tipe = str(g.get("tipe") or "").strip().upper()
        if tipe not in allowed_types:
            tipe = ""
        params = {
            "start_date": str(g.get("from") or "").strip(),
            "end_date": str(g.get("to") or "").strip(),
            "m_org_ids": site_ids,
            "tipe": None if tipe in ("", "all") else tipe,
            "aset": str(g.get("aset") or "").strip() or None,
            "site": None,
            "teknisi": str(g.get("teknisi") or "").strip() or None,
        }
        rows = query_all(COMPARE_RAW_SQL, params)
        groups.append({"label": label, "values": _compute_group_metrics(rows, metrics)})
    if not isinstance(base, int) or base < 0 or base >= len(groups):
        base = 0
    base_label = groups[base]["label"]

    avg = {m["key"]: _num(sum(float(g["values"][m["key"]]) for g in groups) / len(groups))
           for m in metrics}

    rows_out = []
    for i, g in enumerate(groups):
        d_abs = None
        d_pct = None
        if i != base:
            d_abs = {}
            d_pct = {}
            for m in metrics:
                k = m["key"]
                b = float(groups[base]["values"][k])
                v = float(g["values"][k])
                d_abs[k] = _num(v - b)
                d_pct[k] = _num((v - b) / b * 100) if b else None
        rows_out.append({
            "label": g["label"],
            "avg": False,
            "values": g["values"],
            "delta_abs": d_abs,
            "delta_pct": d_pct,
        })
    rows_out.append({"label": "Rata-rata Semua Grup", "avg": True, "values": avg,
                     "delta_abs": None, "delta_pct": None})

    return {
        "metrics": metrics,
        "groups": groups,
        "base_index": base,
        "base_label": base_label,
        "avg": avg,
        "rows": rows_out,
    }


@app.route("/api/refs")
@login_required
def api_refs():
    return jsonify({
        "aset": [r["name"] for r in query_all(COMPARE_REFS_SQL["aset"])],
        "teknisi": [r["name"] for r in query_all(COMPARE_REFS_SQL["teknisi"])],
    })


@app.route("/compare")
@login_required
def compare():
    if not can_compare():
        abort(403)
    return render_template("compare.html", title="Perbandingan Dinamis", today=date.today().isoformat())


@app.route("/api/compare", methods=["POST"])
@login_required
def api_compare():
    if not can_compare():
        return jsonify({"error": "akses ke fitur ini ditolak"}), 403
    data = request.get_json(silent=True) or {}
    try:
        result = build_compare(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@app.route("/api/compare/report", methods=["POST"])
@login_required
def api_compare_report():
    if not can_compare():
        return jsonify({"error": "akses ke fitur ini ditolak"}), 403
    data = request.get_json(silent=True) or {}
    try:
        result = build_compare(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    with open(os.path.join(static_dir, "echarts.min.js"), encoding="utf-8") as f:
        echarts_js = f.read()
    with open(os.path.join(static_dir, "chart.js"), encoding="utf-8") as f:
        chart_js = f.read()
    try:
        with open(os.path.join(static_dir, "logo-petroflexx.png"), "rb") as f:
            logo_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        logo_uri = None

    groups_meta = []
    for g in data.get("groups") or []:
        groups_meta.append({
            "label": g.get("label") or "-",
            "from": g.get("from") or "",
            "to": g.get("to") or "",
            "sites": g.get("sites") or [],
            "tipe": g.get("tipe") or "all",
            "aset": g.get("aset") or "",
            "teknisi": g.get("teknisi") or "",
        })

    html = render_template(
        "compare_report.html",
        dashboard_title=get_dashboard_title(),
        title="Perbandingan Dinamis",
        metrics=result["metrics"],
        rows_json=json.dumps(result["rows"], ensure_ascii=False),
        groups_json=json.dumps(groups_meta, ensure_ascii=False),
        base_label=result["base_label"],
        echarts_js=echarts_js,
        chart_js=chart_js,
        logo_uri=logo_uri,
        generated_by=session.get("full_name") or session.get("user", ""),
        generated_at=date.today().isoformat(),
    )
    try:
        pdf = generate_pdf(html)
    except Exception as exc:
        app.logger.exception("gagal generate pdf perbandingan")
        return jsonify({"error": "gagal generate PDF: %s" % exc}), 500
    filename = "perbandingan-{}.pdf".format(date.today().isoformat())
    resp = Response(pdf, mimetype="application/pdf")
    resp.headers["Content-Disposition"] = "attachment; filename*=UTF-8''{}".format(urllib.parse.quote(filename))
    return resp


from admin import admin_bp

app.register_blueprint(admin_bp, url_prefix="/admin")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8090")))