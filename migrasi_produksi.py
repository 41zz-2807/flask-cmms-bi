import os

import psycopg2


def main():
    sql_path = os.environ.get("SQL_PATH", "/tmp/migrasi_produksi.sql")
    with open(sql_path, encoding="utf-8") as f:
        sql = f.read()
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "1032")),
        dbname=os.environ.get("DB_NAME", "petroflexx_om"),
        user=os.environ.get("DB_USER", "petroflexx_om"),
        password=os.environ.get("DB_PASSWORD", ""),
        options="-c search_path=petroflexx_om",
        connect_timeout=10,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()
    print("MIGRATION OK:", sql_path)


if __name__ == "__main__":
    main()