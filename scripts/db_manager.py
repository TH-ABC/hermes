"""
Quản lý Cơ Sở Dữ Liệu SQL Cục Bộ (SQLite) cho Sever Hermes
Lưu trữ vĩnh viễn tin nhắn và điều phối tệp media (ảnh/video) với Google Drive.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
if not HERMES_HOME.exists():
    HERMES_HOME = Path.home() / ".hermes"

DB_PATH = HERMES_HOME / "hermes_chat.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo bảng Agent_TH chuẩn kiến trúc 4 tầng."""
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS Agent_TH (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT DEFAULT 'all',           -- 'admin', 'hermes', 'local', 'all'
            sender TEXT,                          -- 'Sếp (CEO)', 'Hermes', 'Ant-local'
            role TEXT,                            -- 'admin', 'hermes', 'ant-local'
            message TEXT,                         -- Nội dung tin nhắn
            local_media_path TEXT,                -- Đường dẫn tệp trên máy (C:/.../image.webp)
            drive_link TEXT,                      -- Đường dẫn hoặc liên kết Google Drive
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_synced INT DEFAULT 0,              -- 0: Chưa up Drive, 1: Đã up Drive
            is_cleaned INT DEFAULT 0              -- 0: Còn trên ổ cứng, 1: Đã dọn dẹp sau 3 ngày
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_channel ON Agent_TH(channel);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_created ON Agent_TH(created_at);")
        conn.execute("CREATE VIEW IF NOT EXISTS [Agent-TH] AS SELECT * FROM Agent_TH;")
        conn.commit()


def insert_chat_message(
    channel: str,
    sender: str,
    role: str,
    message: str,
    local_media_path: Optional[str] = None,
    drive_link: Optional[str] = None,
) -> int:
    """Ghi tin nhắn mới vào database."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO Agent_TH (channel, sender, role, message, local_media_path, drive_link, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """,
            (channel, sender, role, message, local_media_path, drive_link),
        )
        conn.commit()
        return cursor.lastrowid


def get_messages(since_id: int = 0, limit: int = 50, channel: str = "all") -> List[Dict[str, Any]]:
    """Truy vấn tin nhắn theo Smart Delta Polling."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        params = []
        sql = "SELECT * FROM Agent_TH WHERE id > ?"
        params.append(since_id)

        if channel != "all":
            sql += " AND (channel = ? OR role = ?)"
            params.extend([channel, channel])

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = cursor.execute(sql, params).fetchall()
        # Đảo lại theo thứ tự thời gian tăng dần
        result = [dict(row) for row in reversed(rows)]
        return result


def get_unsynced_media() -> List[Dict[str, Any]]:
    """Lấy danh sách các file media chưa được đồng bộ sang Google Drive."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT id, local_media_path FROM Agent_TH
            WHERE is_synced = 0 AND local_media_path IS NOT NULL AND local_media_path != ''
            """
        ).fetchall()
        return [dict(row) for row in rows]


def mark_media_synced(msg_id: int, drive_link: str):
    """Cập nhật trạng thái đã đẩy lên Drive."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE Agent_TH SET is_synced = 1, drive_link = ? WHERE id = ?",
            (drive_link, msg_id),
        )
        conn.commit()


def get_old_media_to_clean(days: int = 3) -> List[Dict[str, Any]]:
    """Lấy các tệp đã lưu quá 3 ngày và đã được đồng bộ lên Drive để dọn ổ cứng."""
    init_db()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT id, local_media_path, drive_link FROM Agent_TH
            WHERE is_synced = 1 AND is_cleaned = 0 AND created_at < ?
            AND local_media_path IS NOT NULL AND local_media_path != ''
            """,
            (cutoff,),
        ).fetchall()
        return [dict(row) for row in rows]


def mark_media_cleaned(msg_id: int):
    """Đánh dấu tệp đã dọn dẹp ổ cứng sau 3 ngày."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE Agent_TH SET is_cleaned = 1 WHERE id = ?",
            (msg_id,),
        )
        conn.commit()


if __name__ == "__main__":
    init_db()
    print("SQLite Database HKNT_AgentChat ready at:", str(DB_PATH))
