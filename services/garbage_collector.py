import asyncio
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

def get_gc_settings(db, workspace_id: int) -> dict:
    """Reads the Garbage Collector settings for a given workspace."""
    row = db.conn.execute("SELECT settings_json FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
    if not row or not row[0]:
        return {}
    try:
        data = json.loads(row[0])
        return data.get("garbage_collector", {})
    except json.JSONDecodeError:
        return {}

def schedule_deletion(db, workspace_id: int, chat_id: int, message_id: int, category: str):
    """Schedules a message deletion if the GC module and specific category are enabled."""
    if not workspace_id or not chat_id or not message_id:
        return
        
    settings = get_gc_settings(db, workspace_id)
    if not settings.get("enabled"):
        return
    
    cats = settings.get("categories", {})
    cat_config = cats.get(category)
    if not cat_config or not cat_config.get("enabled"):
        return
        
    delay = int(cat_config.get("delay_seconds", 60))
    # We use local time if the DB uses local time (CURRENT_TIMESTAMP in sqlite is UTC by default)
    # Actually, let's just use UTC for delete_at and check against UTC.
    delete_at = datetime.utcnow() + timedelta(seconds=delay)
    
    db.conn.execute(
        "INSERT INTO scheduled_deletions (workspace_id, chat_id, message_id, category, delete_at) VALUES (?, ?, ?, ?, ?)",
        (workspace_id, chat_id, message_id, category, delete_at)
    )
    db.conn.commit()

async def tick_garbage_collector(bot, db):
    """Background task to delete scheduled messages (runs via scheduler)."""
    try:
        now = datetime.utcnow()
        rows = db.conn.execute(
            "SELECT id, workspace_id, chat_id, message_id, category FROM scheduled_deletions WHERE delete_at <= ?",
            (now,)
        ).fetchall()
        
        for row in rows:
            row_id, ws_id, chat_id, message_id, category = row
            
            # Verify settings are still enabled at deletion time
            settings = get_gc_settings(db, ws_id)
            should_delete = False
            
            if settings.get("enabled"):
                cats = settings.get("categories", {})
                cat_config = cats.get(category)
                if cat_config and cat_config.get("enabled"):
                    should_delete = True
                    
            if should_delete:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception as e:
                    # Log as debug to not spam errors when message is already deleted
                    logger.debug(f"GC failed to delete message {message_id} in {chat_id}: {e}")
                    
            # Always remove the record so we don't get stuck in a loop
            db.conn.execute("DELETE FROM scheduled_deletions WHERE id=?", (row_id,))
            db.conn.commit()
            
    except Exception as e:
        logger.error(f"Error in Garbage Collector tick: {e}")
