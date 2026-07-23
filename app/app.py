import os , time
from flask import Flask, jsonify, request
import psycopg2
from psycopg2 import OperationalError

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "db"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ.get("DB_NAME", "appdb"),
    "user": os.environ.get("DB_USER", "appuser"),
    "password": os.environ.get("DB_PASSWORD", "apppass"),
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Tablo yoksa oluştur. Uygulama başlarken çağrılır."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()
    finally:
        conn.close()

@app.route("/health")
def health():
    """Basit sağlık kontrolü - hem uygulamanın hem DB bağlantısının durumunu döner."""
    try:
        conn = get_connection()
        conn.close()
        db_status = "ok"
    except OperationalError:
        db_status = "unreachable"

    return jsonify({
        "status": "ok",
        "database": db_status,
        "timestamp": time.time(),
    })

@app.route("/notes", methods=["GET"])
def list_notes():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content, created_at FROM notes ORDER BY id DESC LIMIT 20;")
            rows = cur.fetchall()
        notes = [
            {"id": r[0], "content": r[1], "created_at": r[2].isoformat()}
            for r in rows
        ]
        return jsonify(notes)
    finally:
        conn.close()

@app.route("/notes", methods=["POST"])
def create_note():
    data = request.get_json(silent=True) or {}
    content = data.get("content")
    if not content:
        return jsonify({"error": "content alanı zorunlu"}), 400

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notes (content) VALUES (%s) RETURNING id;",
                (content,),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"id": new_id, "content": content}), 201
    finally:
        conn.close()


if __name__ == "__main__":
    # Uygulama başlarken DB'nin hazır olmasını birkaç kez dene
    # (compose'da healthcheck + depends_on kullanacağız ama savunma amaçlı burada da bekleyelim)
    for attempt in range(10):
        try:
            init_db()
            break
        except OperationalError:
            print(f"DB henüz hazır değil, tekrar deneniyor ({attempt + 1}/10)...")
            time.sleep(2)

    app.run(host="0.0.0.0", port=8000)
