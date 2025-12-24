import os, json
from supabase import create_client

SESSION_FILE = os.path.join("config", "session.json")
SUPABASE_CONFIG_FILE = os.path.join("config", "supabase_config.json")

_current_user = None  # {"id": "...", "email": "..."}


def _load_supabase_credentials():
    # 1) Prefer environment variables (Render + local .env)
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    if url and key:
        return url, key

    # 2) Fallback to local JSON for backwards compatibility (but don't deploy/commit it)
    if os.path.exists(SUPABASE_CONFIG_FILE):
        with open(SUPABASE_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        url = (cfg.get("SUPABASE_URL") or "").strip()
        key = (cfg.get("SUPABASE_ANON_KEY") or "").strip()
        if url and key:
            return url, key

    raise RuntimeError(
        "Supabase config not found. Set SUPABASE_URL and SUPABASE_ANON_KEY env vars "
        "or provide config/supabase_config.json locally."
    )


# ONE shared client for the entire app
_supabase_url, _supabase_key = _load_supabase_credentials()
supabase = create_client(_supabase_url, _supabase_key)


def get_supabase():
    return supabase


def get_current_user():
    return _current_user


def _set_current_user(user):
    global _current_user
    if user:
        _current_user = {"id": user.id, "email": user.email}
    else:
        _current_user = None


def save_session(session):
    os.makedirs("config", exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"access_token": session.access_token, "refresh_token": session.refresh_token},
            f,
        )


def load_session():
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("access_token") and data.get("refresh_token"):
            return data
    except Exception:
        pass
    return None


def restore_session_if_any() -> bool:
    data = load_session()
    if not data:
        return False
    try:
        supabase.auth.set_session(data["access_token"], data["refresh_token"])
        u = supabase.auth.get_user()
        if u and u.user:
            _set_current_user(u.user)
            return True
    except Exception as e:
        print("⚠️ restore_session_if_any failed:", repr(e))

    sign_out()
    return False


def sign_in(email: str, password: str):
    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    if res and res.user and res.session:
        save_session(res.session)
        _set_current_user(res.user)
        return get_current_user(), res.session
    return None, None


def sign_up(email: str, password: str, full_name: str | None = None):
    payload = {"email": email, "password": password}
    if full_name:
        payload["options"] = {"data": {"full_name": full_name}}
    return supabase.auth.sign_up(payload)


def sign_out():
    global _current_user
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    if os.path.exists(SESSION_FILE):
        try:
            os.remove(SESSION_FILE)
        except Exception:
            pass

    _current_user = None
    return True
