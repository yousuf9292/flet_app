import uuid
from datetime import datetime, timezone
from app.auth import get_supabase, get_current_user


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


# ----------------- MULTI ASSIGNEES -----------------

def set_task_assignees(task_id: str, assignees: list[str]) -> bool:
    supabase = get_supabase()
    return (
        supabase.table("tasks")
        .update({"assignees": assignees, "updated_at": utc_now_iso()})
        .eq("id", task_id)
        .execute()
    )


# ----------------- TASK CRUD -----------------

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
        "status": "open",
        "pdf_url": None,
        "assignees": [],
        "subtasks": [],
        "comments": [],
        "updated_at": utc_now_iso(),
    }

    supabase.table("tasks").insert(payload).execute()
    return True


def update_task(task_id: str, patch: dict) -> bool:
    supabase = get_supabase()
    user = get_current_user()
    if not user:
        return False

    patch = dict(patch)
    patch["updated_at"] = utc_now_iso()

    supabase.table("tasks").update(patch).eq("id", task_id).execute()
    return True


import json

def fetch_tasks_for_user():
    supabase = get_supabase()
    user = get_current_user()
    if not user:
        return []

    uid = user["id"]

    try:
        owned_res = (
            supabase.table("tasks")
            .select("*")
            .eq("owner", uid)
            .execute()
        )
        owned_tasks = owned_res.data or []

        assigned_res = (
            supabase.table("tasks")
            .select("*")
            .contains("assignees", json.dumps([uid]))
            .execute()
        )
        assigned_tasks = assigned_res.data or []

        return list({t["id"]: t for t in owned_tasks + assigned_tasks}.values())

    except Exception as e:
        print(f"[DEBUG] fetch_tasks_for_user error: {repr(e)}")
        return []



def fetch_task(task_id: str):
    supabase = get_supabase()
    res = supabase.table("tasks").select("*").eq("id", task_id).single().execute()
    return res.data if res.data else {}


def delete_task(task_id: str) -> bool:
    supabase = get_supabase()
    supabase.table("tasks").delete().eq("id", task_id).execute()
    return True


def fetch_clients():
    sb = get_supabase()
    return sb.table("clients").select("*").execute().data or []


def add_client(payload: dict):
    sb = get_supabase()
    user = get_current_user()
    payload["owner"] = user["id"]
    res = sb.table("clients").insert(payload).execute()
    return res.data[0] if res.data else None


def update_client(client_id: str, payload: dict):
    sb = get_supabase()
    sb.table("clients").update(payload).eq("id", client_id).execute()


def delete_client(client_id: str):
    sb = get_supabase()
    sb.table("clients").delete().eq("id", client_id).execute()

# ----------------- BACKWARD COMPAT (optional) -----------------

def set_task_assignee(task_id: str, assignee_id: str | None) -> bool:
    assignees = [assignee_id] if assignee_id else []
    return set_task_assignees(task_id, assignees)


def set_task_subtasks(task_id: str, subtasks: list) -> bool:
    return update_task(task_id, {"subtasks": subtasks})


def set_task_comments(task_id: str, comments: list) -> bool:
    return update_task(task_id, {"comments": comments})


def set_task_pdf(task_id: str, pdf_url: str | None, status: str) -> bool:
    return update_task(task_id, {"pdf_url": pdf_url, "status": status})
