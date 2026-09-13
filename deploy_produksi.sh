#!/usr/bin/env bash
# ============================================================
# Deploy BI CMMS Flask -> VPS PRODUKSI (host ompetroflexx)
# ARSITEKTUR 2 DATABASE:
#   1) DB APLIKASI (docker postgres existing untuk app Flask):
#      berisi bi_user, bi_settings, bi_user_detail_access.
#      Ditunjuk via env DB_* di prod.env.
#   2) DB DATA CMMS (readonly): jdbc:postgresql://localhost:1032/petroflexx_om
#      user petroflexx_om. DIATUR lewat override di panel superadmin
#      (Pengaturan Database CMMS). Koneksi data dipaksa read-only oleh db.py.
# Asumsi: folder repo ini sudah ada di VPS, Docker aktif,
#         /opt/tomcat/media berisi WO (2023-2026, FORM).
# Cara pakai di VPS:  bash deploy_produksi.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="prod.env"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file prod.env"
RED="\033[0;31m"; GRN="\033[0;32m"; CYN="\033[0;36m"; NC="\033[0m"

log(){ printf "${CYN}[deploy]${NC} %s\n" "$*"; }
ok(){  printf "${GRN}[+]${NC} %s\n" "$*"; }
err(){ printf "${RED}[-]${NC} %s\n" "$*"; }

# ---------- 1. prod.env (generated SECRET_KEY) ----------
if [[ ! -f "$ENV_FILE" ]]; then
  log "Membuat $ENV_FILE baru (default: DB APLIKASI docker di 127.0.0.1:5432, port app 8090)."
  cat > "$ENV_FILE" <<EOF
# Dibuat oleh deploy_produksi.sh $(date -Iseconds)
# DB APLIKASI (docker postgres ikannya-baba-db:5432 - database cmms_flash)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=cmms_flash
DB_USER=cmms_flash
DB_PASSWORD=
DASHBOARD_TITLE=Aplikasi CMMS - Petroflexx OM
MEDIA_ROOT=/opt/tomcat/media
MEDIA_WO_PATH=/opt/tomcat/media/WO
PORT=8090
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SUPERADMIN_PASSWORD=
EOF
  ok "$ENV_FILE dibuat. Isi DB_PASSWORD (db cmms_flash), TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID, dan SUPERADMIN_PASSWORD (nilai awal superadmin ada di NOTES.md yang gitignored)."
fi

if ! grep -q '^SECRET_KEY=.' "$ENV_FILE"; then
  if command -v openssl >/dev/null 2>&1; then
    KEY="$(openssl rand -hex 32)"
  elif command -v python3 >/dev/null 2>&1; then
    KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  else
    KEY="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  sed -i '/^SECRET_KEY=.*/d' "$ENV_FILE"
  printf "SECRET_KEY=%s\n" "$KEY" >> "$ENV_FILE"
  ok "SECRET_KEY digenerate: $KEY"
else
  ok "SECRET_KEY sudah ada di $ENV_FILE."
fi

for key in DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD DASHBOARD_TITLE MEDIA_ROOT MEDIA_WO_PATH PORT TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID SUPERADMIN_PASSWORD; do
  grep -q "^${key}=" "$ENV_FILE" || printf "%s=\n" "$key" >> "$ENV_FILE"
done

# Dicatat: container app pakai network_mode: host, jadi DB APLIKASI docker
# harus ter-publish di host (mis. -p 5432:5432) agar bisa diakses 127.0.0.1:DB_PORT.
log "Isi $ENV_FILE (DB_PASSWORD disensor):"
sed -E 's/^(DB_PASSWORD=).*/\1****/' "$ENV_FILE"

PORT="$(sed -n 's/^PORT=//p' "$ENV_FILE")"
PORT="${PORT:-8090}"

# ---------- 2. validasi compose ----------
log "Validasi docker-compose.prod.yml..."
$COMPOSE config --quiet
ok "Compose valid."

# ---------- 3. build & start ----------
log "Build image dan start container (bind 127.0.0.1:${PORT})..."
$COMPOSE up -d --build

# ---------- 4. migrasi DB aplikasi ----------
log "Migrasi tabel aplikasi di schema petroflexx_om (idempotent)..."
$COMPOSE run --rm --no-deps \
  -v "$PWD/migrasi_produksi.sql:/tmp/migrasi_produksi.sql:ro" \
  -v "$PWD/migrasi_produksi.py:/tmp/migrasi_produksi.py:ro" \
  web python /tmp/migrasi_produksi.py

# ---------- 5. tes login superadmin ----------
SA_PASS="$(sed -n 's/^SUPERADMIN_PASSWORD=//p' "$ENV_FILE")"
if [[ -z "$SA_PASS" ]]; then
  err "SUPERADMIN_PASSWORD kosong di $ENV_FILE -> tes login dilewati (isi dulu lalu jalankan ulang)."
else
  log "Tes login superadmin..."
  sleep 8
  if command -v curl >/dev/null 2>&1; then
    CODE="$(curl -s -o /dev/null -w '%{http_code}' -c /tmp/dep_sa.txt -b /tmp/dep_sa.txt \
      --data-urlencode "username=superadmin" --data-urlencode "password=$SA_PASS" "http://127.0.0.1:${PORT}/login" || true)"
    rm -f /tmp/dep_sa.txt
  else
    CODE="$(PORT="$PORT" SA_PASS="$SA_PASS" python3 - <<PY || true
import os, urllib.request, urllib.parse, http.cookiejar
port, sa = os.environ["PORT"], os.environ["SA_PASS"]
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
data = urllib.parse.urlencode({"username": "superadmin", "password": sa}).encode()
req = urllib.request.Request(f"http://127.0.0.1:{port}/login", data=data, method="POST")
try:
    r = op.open(req, timeout=15)
    print(r.status)
except urllib.error.HTTPError as e:
    print(e.code)
PY
)"
  fi
  if [[ "$CODE" == "302" ]]; then
    ok "Login superadmin OK (302). Panel: http://<ip-vps>:${PORT}/"
  else
    err "Login superadmin: HTTP $CODE (bukan 302). Cek log: $COMPOSE logs"
  fi
fi

# ---------- 6. catatan (Data CMMS readonly via panel) ----------
log "Selesai. Langkah berikutnya:"
echo "  1. Login superadmin -> panel 'Data CMMS' -> aktifkan override:"
echo "     host 127.0.0.1, port 1032, db petroflexx_om, user petroflexx_om, password (isi)."
echo "     Koneksi data DIPAKSA read-only oleh db.py -> data CMMS tidak pernah di-UPDATE."
echo "  2. Ganti password superadmin lewat Panel > Pengguna > Reset."
echo "  3. Reverse proxy nginx + HTTPS (certbot/npm): 80/443 -> 127.0.0.1:${PORT}."
echo "  4. Firewall: hanya buka 22, 80, 443 (1032/5432/8090 biarkan lokal)."
echo "  5. Backup rutin: pg_dump -h 127.0.0.1 -p <app_db_port> -U <app_user> -d petroflexx_om"