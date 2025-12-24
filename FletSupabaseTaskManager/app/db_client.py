import uuid
from datetime import datetime, timezone
from app.auth import get_supabase, get_current_user


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def add_task(title: str, description: str = "") -> bool:
    supabase = get_supabase()
    user = get_current_user()
    if not user:
        return False

    payload = {
        "id": str(uuid.uuid4()),
        "owner": user["id"],
        "title": title,
        "description": description,
        "subtasks": [],
        "comments": [],
        "updated_at": utc_now_iso(),
    }
    supabase.table("tasks").insert(payload).execute()
    return True


def fetch_tasks_for_user():
    supabase = get_supabase()
    user = get_current_user()
    if not user:
        return []

    res = (
        supabase.table("tasks")
        .select("*")
        .or_(f"owner.eq.{user['id']},assignee.eq.{user['id']}")
        .order("updated_at", desc=True)
        .execute()
    )
    return res.data or []


def delete_task(task_id: str) -> bool:
    supabase = get_supabase()
    supabase.table("tasks").delete().eq("id", task_id).execute()
    return True
