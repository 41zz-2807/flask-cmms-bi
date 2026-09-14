import re
import smtplib
from email.message import EmailMessage
from functools import wraps

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import ADMIN_ROLES, APP_VERSION_FULL, FOLDER_COLORS, LICENSE_TEXT, get_dashboard_title
from auth import hash_password
from db import allowed_categories, category_overrides, execute, query_all
from queries import QUERIES

admin_bp = Blueprint("admin", __name__, template_folder="templates")

CATEGORIES = [{"key": k, "title": cfg["title"]} for k, cfg in QUERIES.items()]

DB_KEYS = ("db_override_enabled", "db_host", "db_port", "db_name", "db_user", "db_password")
SMTP_KEYS = ("smtp_enabled", "smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_from", "smtp_use_tls")

_USERS_SQL = """
    SELECT u.username, COALESCE(u.full_name, '') AS full_name, u.role, u.is_active, u.created_at,
           (SELECT count(*) FROM bi_user_detail_access a WHERE a.bi_username = u.username) AS n_access
    FROM bi_user u
    ORDER BY (u.role = 'superadmin') DESC, u.username
"""


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = session.get("user")
        if not user:
            return redirect(url_for("login", next=request.path))
        if session.get("role") not in ADMIN_ROLES:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def load_settings():
    rows = query_all("SELECT key, value FROM bi_settings", admin=True)
    return {r["key"]: r["value"] for r in rows}


def save_setting(key, value):
    execute(
        "INSERT INTO bi_settings (key, value, value_type, updated_at) "
        "VALUES (%s, %s, 'text', now()) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
        (key, value),
        admin=True,
    )


@admin_bp.route("/")
@admin_required
def dashboard():
    users = query_all(_USERS_SQL, admin=True)
    settings = load_settings()
    n_users = len(users)
    n_active = sum(1 for u in users if u["is_active"])
    n_visible = sum((u.get("n_access") or 0) for u in users if u["username"] != "superadmin")
    return render_template(
        "admin/dashboard.html",
        n_users=n_users,
        n_active=n_active,
        n_visible=n_visible,
        settings=settings,
        categories=CATEGORIES,
        app_version=APP_VERSION_FULL,
        dashboard_title=get_dashboard_title(),
        license_text=LICENSE_TEXT,
    )


@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        full_name = (request.form.get("full_name") or "").strip()
        password = request.form.get("password") or ""
        role = (request.form.get("role") or "user").strip()
        if role not in ("user", "superadmin"):
            role = "user"
        if not re.fullmatch(r"[a-zA-Z0-9_.\-]{1,50}", username):
            flash("Username tidak valid (hanya huruf/angka/._-).", "error")
        elif len(password) < 6:
            flash("Password minimal 6 karakter.", "error")
        elif query_all("SELECT 1 FROM bi_user WHERE username = %(u)s", {"u": username}, admin=True):
            flash("Username '{}' sudah digunakan.".format(username), "error")
        else:
            execute(
                "INSERT INTO bi_user (username, password_hash, full_name, role, is_active, created_at) "
                "VALUES (%s, %s, %s, %s, true, now())",
                (username, hash_password(password), full_name or username, role),
                admin=True,
            )
            flash("User '{}' berhasil ditambahkan.".format(username), "ok")
            return redirect(url_for("admin.users"))
    return render_template(
        "admin/users.html",
        users=query_all(_USERS_SQL, admin=True),
        categories=CATEGORIES,
        app_version=APP_VERSION_FULL,
        dashboard_title=get_dashboard_title(),
        license_text=LICENSE_TEXT,
    )


@admin_bp.route("/users/<username>/reset", methods=["POST"])
@admin_required
def user_reset(username):
    password = (request.form.get("password") or "").strip()
    if len(password) < 6:
        flash("Password minimal 6 karakter.", "error")
        return redirect(url_for("admin.users", _anchor=username))
    execute(
        "UPDATE bi_user SET password_hash = %s, updated_at = now() WHERE username = %s",
        (hash_password(password), username),
        admin=True,
    )
    flash("Password '{}' berhasil direset.".format(username), "ok")
    return redirect(url_for("admin.users", _anchor=username))


@admin_bp.route("/users/<username>/toggle", methods=["POST"])
@admin_required
def user_toggle(username):
    if username == "superadmin":
        flash("Akun superadmin tidak boleh dinonaktifkan.", "error")
        return redirect(url_for("admin.users"))
    execute(
        "UPDATE bi_user SET is_active = NOT is_active, updated_at = now() WHERE username = %s",
        (username,),
        admin=True,
    )
    flash("Status user '{}' diubah.".format(username), "ok")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<username>/role", methods=["POST"])
@admin_required
def user_role(username):
    role = (request.form.get("role") or "user").strip()
    if role not in ("user", "superadmin"):
        role = "user"
    if username == "superadmin" and role != "superadmin":
        flash("Role akun superadmin tidak bisa diturunkan.", "error")
        return redirect(url_for("admin.users"))
    execute("UPDATE bi_user SET role = %s, updated_at = now() WHERE username = %s", (role, username), admin=True)
    flash("Role '{}' sekarang: {}".format(username, role), "ok")
    return redirect(url_for("admin.users"))


@admin_bp.route("/access")
@admin_required
def access():
    users = query_all(_USERS_SQL, admin=True)
    return render_template(
        "admin/access.html",
        users=users,
        categories=CATEGORIES,
        app_version=APP_VERSION_FULL,
        dashboard_title=get_dashboard_title(),
        license_text=LICENSE_TEXT,
    )


@admin_bp.route("/users/<username>/access", methods=["GET", "POST"])
@admin_required
def user_access(username):
    row = query_all("SELECT role FROM bi_user WHERE username = %(u)s", {"u": username}, admin=True)
    if not row:
        abort(404)
    if request.method == "POST":
        selected = [c for c in request.form.getlist("categories") if c == "compare" or c in QUERIES]
        execute("DELETE FROM bi_user_detail_access WHERE bi_username = %s", (username,), admin=True)
        for c in selected:
            execute(
                "INSERT INTO bi_user_detail_access (bi_username, category) VALUES (%s, %s)",
                (username, c),
                admin=True,
            )
        flash("Akses dashboard '{}' diperbarui ({} kategori).".format(username, len(selected)), "ok")
        return redirect(url_for("admin.user_access", username=username))
    current = allowed_categories(username)
    return render_template(
        "admin/user_access.html",
        username=username,
        role=row[0]["role"],
        categories=CATEGORIES,
        current=current,
        app_version=APP_VERSION_FULL,
        dashboard_title=get_dashboard_title(),
        license_text=LICENSE_TEXT,
    )


@admin_bp.route("/server", methods=["GET", "POST"])
@admin_required
def server():
    if request.method == "POST":
        port = (request.form.get("db_port") or "").strip()
        if port and not port.isdigit():
            flash("DB Port harus berupa angka.", "error")
            return redirect(url_for("admin.server"))
        save_setting("db_override_enabled", "1" if request.form.get("db_override_enabled") == "1" else "0")
        for k in ("db_host", "db_port", "db_name", "db_user"):
            val = (request.form.get(k) or "").strip()
            if k == "db_port" and not val:
                continue
            if val:
                save_setting(k, val)
        pw = (request.form.get("db_password") or "").strip()
        if pw:
            save_setting("db_password", pw)
        flash("Pengaturan database disimpan.", "ok")
        return redirect(url_for("admin.server"))
    return render_template(
        "admin/server.html",
        settings=load_settings(),
        app_version=APP_VERSION_FULL,
        dashboard_title=get_dashboard_title(),
        license_text=LICENSE_TEXT,
    )


_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@admin_bp.route("/appearance", methods=["GET", "POST"])
@admin_required
def appearance():
    if request.method == "POST":
        new_title = (request.form.get("dashboard_title") or "").strip()
        if len(new_title) > 120:
            flash("Judul dashboard maksimal 120 karakter.", "error")
            return redirect(url_for("admin.appearance"))
        save_setting("dashboard_title", new_title)
        rows = []
        bad = None
        for key, cfg in QUERIES.items():
            t = (request.form.get("t_{}".format(key)) or "").strip()
            c = (request.form.get("c_{}".format(key)) or "").strip()
            if t == cfg["title"]:
                t = ""
            if len(t) > 120:
                bad = "judul '{}' melebihi 120 karakter".format(cfg["title"])
                break
            if c and not _COLOR_RE.fullmatch(c):
                bad = "warna '{}' tidak valid (format #RRGGBB)".format(cfg["title"])
                break
            rows.append((key, t, c))
        if bad:
            flash("Gagal menyimpan: " + bad, "error")
            return redirect(url_for("admin.appearance"))
        execute("DELETE FROM petroflexx_om.bi_dashboard_category", admin=True)
        for key, t, c in rows:
            if t or c:
                execute(
                    "INSERT INTO petroflexx_om.bi_dashboard_category (category, title, color, updated_at) "
                    "VALUES (%s, %s, %s, now())",
                    (key, t or None, c or None),
                    admin=True,
                )
        flash("Tampilan dashboard diperbarui.", "ok")
        return redirect(url_for("admin.appearance"))
    overrides = category_overrides()
    items = []
    for i, (key, cfg) in enumerate(QUERIES.items()):
        ov = overrides.get(key) or {}
        items.append({
            "key": key,
            "title": cfg["title"],
            "custom_title": ov.get("title") or "",
            "color": ov.get("color") or FOLDER_COLORS[i % len(FOLDER_COLORS)],
            "custom_color": ov.get("color") or "",
        })
    return render_template(
        "admin/appearance.html",
        dashboard_title_now=get_dashboard_title(),
        items=items,
        app_version=APP_VERSION_FULL,
        dashboard_title=get_dashboard_title(),
        license_text=LICENSE_TEXT,
    )


@admin_bp.route("/smtp/test", methods=["POST"])
@admin_required
def smtp_test():
    to_addr = (request.form.get("to_email") or "").strip()
    settings = load_settings()
    host = (settings.get("smtp_host") or "").strip()
    port = (settings.get("smtp_port") or "").strip()
    user = (settings.get("smtp_username") or "").strip()
    pw = settings.get("smtp_password") or ""
    from_addr = (settings.get("smtp_from") or "").strip()
    use_tls = settings.get("smtp_use_tls") == "1"
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to_addr):
        flash("Alamat tujuan test email tidak valid.", "error")
        return redirect(url_for("admin.smtp"))
    if not (host and port and from_addr):
        flash("Konfigurasi SMTP belum lengkap. Simpan pengaturan di atas dulu.", "error")
        return redirect(url_for("admin.smtp"))
    try:
        msg = EmailMessage()
        msg["Subject"] = "Test Email | Konfigurasi SMTP - {}".format(get_dashboard_title())
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(
            "Ini adalah email test dari panel administrasi {}.\n"
            "Jika Anda menerima email ini, konfigurasi SMTP berfungsi dengan benar.\n\n"
            "Host: {}\nPort: {}\nUsername: {}\nTLS: {}".format(
                get_dashboard_title(), host, port, user or "(tanpa login)", "Ya" if use_tls else "Tidak"
            )
        )
        if str(port) == "465":
            server = smtplib.SMTP_SSL(host, int(port), timeout=15)
        else:
            server = smtplib.SMTP(host, int(port), timeout=15)
            if use_tls:
                server.starttls()
        with server:
            if user:
                server.login(user, pw)
            server.send_message(msg)
        flash("Test email berhasil dikirim ke '{}'.".format(to_addr), "ok")
    except Exception as exc:
        flash("Test email GAGAL: {}".format(exc), "error")
    return redirect(url_for("admin.smtp"))


@admin_bp.route("/smtp", methods=["GET", "POST"])
@admin_required
def smtp():
    if request.method == "POST":
        required = ("smtp_host", "smtp_port", "smtp_username", "smtp_from")
        missing = [k for k in required if not (request.form.get(k) or "").strip()]
        if missing:
            flash("Kolom wajib diisi: " + ", ".join(k.replace("smtp_", "").replace("_", " ") for k in missing), "error")
            return redirect(url_for("admin.smtp"))
        if not (request.form.get("smtp_port") or "").strip().isdigit():
            flash("SMTP Port harus berupa angka.", "error")
            return redirect(url_for("admin.smtp"))
        save_setting("smtp_enabled", "1" if request.form.get("smtp_enabled") == "1" else "0")
        save_setting("smtp_use_tls", "1" if request.form.get("smtp_use_tls") == "1" else "0")
        for k in ("smtp_host", "smtp_port", "smtp_username", "smtp_from"):
            save_setting(k, (request.form.get(k) or "").strip())
        pw = (request.form.get("smtp_password") or "").strip()
        if pw:
            save_setting("smtp_password", pw)
        flash("Pengaturan email (SMTP) disimpan.", "ok")
        return redirect(url_for("admin.smtp"))
    return render_template(
        "admin/smtp.html",
        settings=load_settings(),
        app_version=APP_VERSION_FULL,
        dashboard_title=get_dashboard_title(),
        license_text=LICENSE_TEXT,
    )