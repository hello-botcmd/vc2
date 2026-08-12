import os
import sqlite3

DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "mirror.db")


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS message_map (
            source_msg_id INTEGER PRIMARY KEY,
            dest_msg_id   INTEGER NOT NULL,
            source_chat   INTEGER,
            dest_chat     INTEGER,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_mapping(source_msg_id: int, dest_msg_id: int, source_chat: int, dest_chat: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO message_map "
        "(source_msg_id, dest_msg_id, source_chat, dest_chat) VALUES (?, ?, ?, ?)",
        (source_msg_id, dest_msg_id, source_chat, dest_chat),
    )
    conn.commit()
    conn.close()


def get_dest_msg_id(source_msg_id: int):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT dest_msg_id FROM message_map WHERE source_msg_id = ?", (source_msg_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def delete_mapping(source_msg_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM message_map WHERE source_msg_id = ?", (source_msg_id,))
    conn.commit()
    conn.close()
