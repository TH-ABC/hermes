"""
Background Sync & Retention Worker cho Google Drive:
1. Đồng bộ ngầm ảnh/video từ Sever Hermes sang thư mục Google Drive (Hermes_Media_Vault).
2. Tự động kiểm tra file quá 3 ngày: dọn dẹp file gốc trên ổ cứng để không đầy máy.
3. Cập nhật đường link Cloud Drive vào SQLite HKNT_AgentChat.
"""

import os
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

try:
    import db_manager
except ImportError:
    from . import db_manager

HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
if not HERMES_HOME.exists():
    HERMES_HOME = Path.home() / ".hermes"

IMAGE_CACHE_DIR = HERMES_HOME / "image_cache"
VIDEO_CACHE_DIR = HERMES_HOME / "video_cache"
RECEIVED_IMAGES_DIR = ROOT_DIR / "received_images"


def find_google_drive_path() -> Path | None:
    """Tự động tìm kiếm ổ đĩa Google Drive trên Windows."""
    # 1. Quét các ổ đĩa ảo từ G đến Z
    possible_drives = [f"{chr(d)}:\\" for d in range(ord('G'), ord('Z') + 1)]
    for drive_root in possible_drives:
        p = Path(drive_root)
        if p.exists():
            for sub in ["My Drive", "Drive của tôi", "Mon Drive", ""]:
                candidate = p / sub if sub else p
                if candidate.exists() and (candidate / "My Drive").exists():
                    return candidate / "My Drive"
                if candidate.exists() and sub:
                    return candidate

    # 2. Quét thư mục người dùng
    user_home = Path.home()
    for sub in ["Google Drive", "GoogleDrive", "OneDrive"]:
        candidate = user_home / sub
        if candidate.exists():
            return candidate

    return None


def run_sync_cycle():
    """Chu kỳ đồng bộ media lên Drive và dọn dẹp sau 3 ngày."""
    drive_root = find_google_drive_path()
    if not drive_root:
        print("[Drive Sync] Cloud Drive folder not detected yet. Waiting for Google Drive desktop...")
        return

    vault_dir = drive_root / "Hermes_Media_Vault"
    vault_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Drive Sync] Cloud Vault directory: {vault_dir}")

    # 1. Đồng bộ các file trong hàng đợi chưa sync
    unsynced = db_manager.get_unsynced_media()
    for item in unsynced:
        msg_id = item["id"]
        local_p = Path(item["local_media_path"])
        if local_p.exists():
            target_dest = vault_dir / local_p.name
            try:
                shutil.copy2(str(local_p), str(target_dest))
                print(f"[Drive Sync] Synced to Cloud Vault: {local_p.name}")
                db_manager.mark_media_synced(msg_id, str(target_dest))
            except Exception as e:
                print(f"[Drive Sync] Error copying {local_p.name}: {e}")

    # Đồng bộ thêm các file trong image_cache và video_cache nếu chưa có trong vault
    for cache_dir in [IMAGE_CACHE_DIR, VIDEO_CACHE_DIR, RECEIVED_IMAGES_DIR]:
        if not cache_dir.exists():
            continue
        for f in cache_dir.glob("*.*"):
            if f.is_file() and f.suffix.lower() in [".webp", ".png", ".jpg", ".jpeg", ".mp4", ".mov"]:
                dest = vault_dir / f.name
                if not dest.exists():
                    try:
                        shutil.copy2(str(f), str(dest))
                        print(f"[Drive Sync] Auto sync new media: {f.name}")
                    except Exception:
                        pass

    # 2. Dọn dẹp các file quá 3 ngày (3-day Retention Policy)
    old_items = db_manager.get_old_media_to_clean(days=3)
    for old in old_items:
        msg_id = old["id"]
        local_p = Path(old["local_media_path"])
        if local_p.exists():
            try:
                os.remove(str(local_p))
                print(f"[Clean 3-Day] Cleaned local file after 3 days (backed up to Drive): {local_p.name}")
                db_manager.mark_media_cleaned(msg_id)
            except Exception as e:
                print(f"[Clean 3-Day] Error cleaning file {local_p.name}: {e}")


if __name__ == "__main__":
    db_manager.init_db()
    print("[Drive Sync] Starting Google Drive sync & retention check...")
    run_sync_cycle()
