-- ============================================================
-- Migrasi DB APLIKASI BI CMMS - schema petroflexx_om (idempotent)
-- JALANKAN di DB APLIKASI (docker postgres, ditunjuk env DB_*),
-- BUKAN di DB Data CMMS (localhost:1032) yang hanya readonly.
-- Aman dijalankan ulang.
-- ============================================================
SET search_path = petroflexx_om;

CREATE TABLE IF NOT EXISTS bi_user (
    username      text PRIMARY KEY,
    password_hash text NOT NULL,
    full_name     text,
    role          text NOT NULL DEFAULT 'user',
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz
);

ALTER TABLE bi_user ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'user';

CREATE TABLE IF NOT EXISTS bi_settings (
    key        text PRIMARY KEY,
    value      text,
    value_type text NOT NULL DEFAULT 'text',
    updated_at timestamptz
);

CREATE TABLE IF NOT EXISTS bi_user_detail_access (
    bi_username text NOT NULL REFERENCES bi_user (username) ON DELETE CASCADE,
    category    text NOT NULL,
    PRIMARY KEY (bi_username, category)
);

-- Tampilan dashboard custom: judul & warna per kategori folder
-- (overrides judul folder/warna; GRANT DML ke role app bisnis harus dilakukan manual)
CREATE TABLE IF NOT EXISTS bi_dashboard_category (
    category   text PRIMARY KEY,
    title      text,
    color      text,
    updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_user_detail_access_username
    ON bi_user_detail_access (bi_username);

INSERT INTO bi_user (username, password_hash, full_name, role, is_active, created_at)
VALUES (
    'superadmin',
    'pbkdf2:sha256:200000$5b3ca68336cd1f49960d6d7f4beb1c97$e6bdec186bd4ae355d25229decd7a4cb858339511a6dad46741e8aa88f3224b5',
    'Super Administrator',
    'superadmin',
    true,
    now()
)
ON CONFLICT (username) DO UPDATE
    SET role = 'superadmin', is_active = true;