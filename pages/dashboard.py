import os
import uuid
import json
from datetime import datetime
from io import BytesIO

import flet as ft
from app.auth import get_current_user, sign_out, get_supabase
from app.db_client import (
    add_task,
    fetch_tasks_for_user,
    delete_task,
    update_task,
    set_task_subtasks,
    set_task_assignees,
    set_task_comments,
    set_task_pdf,
    fetch_task,
)

UPLOAD_DIR = "uploads"
PDF_BUCKET = "ssr-reports"


class DashboardPage(ft.Container):
    def __init__(self, page: ft.Page, on_logout):
        super().__init__()
        self.page = page
        self.on_logout = on_logout
        self.expand = True
        self.padding = 12
        self.bgcolor = ft.Colors.BLUE_GREY_50
        self.page.snack_bar = ft.SnackBar(content=ft.Text(""), open=False)
        self.supabase = get_supabase()
        self.user = get_current_user() or {}

        # Users map
        self.users_map = {}
        self._load_users()

        # File picker for PDF
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        self.file_picker = ft.FilePicker(
            on_result=self._on_file_picked,
            on_upload=self._on_file_upload,
        )
        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)

        # Pending upload state
        self._pending_pdf = None
        self._pending_subtask_pdf=None
        # {"task_id":..., "subtask_id":..., "filename":..., "storage_key":...}

        # Inputs
        self.title_f = ft.TextField(label="Task title", expand=True)
        self.desc_f = ft.TextField(label="Description", expand=True)

        self.add_btn = ft.ElevatedButton("➕ Add", on_click=self.add_clicked)
        self.refresh_btn = ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", on_click=lambda e: self.refresh())
        self.logout_btn = ft.OutlinedButton("Logout", on_click=self.logout)

        self.tasks_view = ft.ListView(expand=True, spacing=10, padding=8)

        header = ft.Row(
            [
                ft.Text(f"Welcome, {self.user.get('email','user')}", size=16, weight="bold", expand=True),
                ft.IconButton(
                    ft.Icons.TABLE_VIEW,
                    tooltip="Table View",
                    on_click=lambda e: self.page.go("/table"),
                ),
                self.refresh_btn,
                self.logout_btn,
            ]
        )

        self.content = ft.Column(
            [
                header,
                ft.Row([self.title_f, self.desc_f, self.add_btn]),
                ft.Divider(),
                self.tasks_view,
            ],
            expand=True,
        )

        self.refresh()

    # ----------------- helpers -----------------
    def toast(self, msg: str):
        sb = ft.SnackBar(content=ft.Text(msg), open=True)
        self.page.snack_bar = sb
        self.page.update()
        print("[TOAST]", msg)

    def _as_list(self, val):
        if val is None:
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val) if val else []
            except Exception:
                return []
        return []

    def _load_users(self):
        try:
            users = self.supabase.table("profiles").select("id,email,full_name").execute().data or []
            self.users_map = {
                u["id"]: (u.get("full_name") or u.get("email") or u["id"][:6])
                for u in users
                if u.get("id")
            }
        except Exception as e:
            print("⚠️ load users failed:", repr(e))
            self.users_map = {}

    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    # ----------------- rendering -----------------
    def refresh(self):
        self._load_users()
        self.tasks_view.controls.clear()
        tasks = fetch_tasks_for_user()
        if not tasks:
            self.tasks_view.controls.append(ft.Text("No tasks yet."))
        else:
            for t in tasks:
                self.tasks_view.controls.append(self._task_card(t))
        self.page.update()

    def _task_card(self, task: dict) -> ft.Control:
        status = (task.get("status") or "open").lower()
        pdf_url = task.get("pdf_url")

        assignees = self._as_list(task.get("assignees"))
        assignee_labels = [self.users_map.get(uid, uid[:6]) for uid in assignees]
        assignee_text = ", ".join(assignee_labels) if assignee_labels else "Unassigned"

        subtasks = self._as_list(task.get("subtasks"))
        comments = self._as_list(task.get("comments"))

        status_color = ft.Colors.GREEN if status == "closed" else ft.Colors.ORANGE
        subs_ui = ft.Column([self._subtask_row(task, s) for s in subtasks], spacing=4) \
            if subtasks else ft.Text("No subtasks", size=12, color=ft.Colors.GREY)

        pdf_buttons = []
        if not pdf_url:
            pdf_buttons.append(
                ft.OutlinedButton("Attach PDF (close task)", on_click=lambda e, t=task: self._attach_pdf(t))
            )
        else:
            pdf_buttons.append(ft.OutlinedButton("Open PDF", on_click=lambda e, url=pdf_url: self.page.launch_url(url)))
            pdf_buttons.append(
                ft.OutlinedButton(
                    "Remove PDF (re-open)",
                    on_click=lambda e, t=task: self._remove_pdf(t),
                    style=ft.ButtonStyle(color=ft.Colors.RED),
                )
            )

        return ft.Card(
            ft.Container(
                padding=12,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(task.get("title", ""), size=16, weight="bold", expand=True),
                                ft.IconButton(ft.Icons.EDIT, tooltip="Edit", on_click=lambda e, t=task: self._edit_task_dialog(t)),
                                ft.IconButton(ft.Icons.DELETE, tooltip="Delete", icon_color=ft.Colors.RED,
                                              on_click=lambda e, t=task: self._delete_confirm(t)),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(task.get("description") or "—", color=ft.Colors.GREY_800),
                        ft.Row(
                            [
                                ft.Text(f"Status: {status}", color=status_color),
                                ft.Text(f"Assigned to: {assignee_text}", color=ft.Colors.BLUE_GREY, expand=True),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(),
                        ft.Text("Subtasks", weight="bold"),
                        subs_ui,
                        ft.Row(
                            [
                                ft.OutlinedButton("Add subtask", on_click=lambda e, t=task: self._add_subtask_dialog(t)),
                                ft.OutlinedButton("Assign", on_click=lambda e, t=task: self._assign_dialog(t)),
                                ft.OutlinedButton(f"Comments ({len(comments)})", on_click=lambda e, t=task: self._comments_dialog(t)),
                            ],
                            wrap=True,
                        ),
                        ft.Divider(),
                        *pdf_buttons,
                    ],
                    spacing=8,
                ),
            )
        )

    # ----------------- CRUD -----------------
    def add_clicked(self, e):
        title = (self.title_f.value or "").strip()
        desc = (self.desc_f.value or "").strip()
        if not title:
            return self.toast("⚠️ Enter a title")
        try:
            ok = add_task(title, desc)
            if ok:
                self.title_f.value = ""
                self.desc_f.value = ""
                self.toast("✅ Added")
                self.refresh()
            else:
                self.toast("❌ Not logged in")
        except Exception as ex:
            print("❌ add task error:", repr(ex))
            self.toast(f"❌ Failed: {ex}")

    def _edit_task_dialog(self, task: dict):
        title_f = ft.TextField(label="Title", value=task.get("title", ""))
        desc_f = ft.TextField(label="Description", value=task.get("description", ""), multiline=True)

        def save(e):
            try:
                update_task(task["id"], {"title": title_f.value, "description": desc_f.value})
                dlg.open = False
                self.toast("✅ Updated")
                self.refresh()
            except Exception as ex:
                print("❌ edit failed:", repr(ex))
                self.toast(f"❌ Update failed: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Edit Task"),
            content=ft.Column([title_f, desc_f], tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton("Save", on_click=save),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _delete_confirm(self, task: dict):
        def confirm(e):
            try:
                delete_task(task["id"])
                dlg.open = False
                self.toast("🗑️ Deleted")
                self.refresh()
            except Exception as ex:
                print("❌ delete failed:", repr(ex))
                self.toast(f"❌ Delete failed: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Delete '{task.get('title','')}'?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton("Delete", on_click=confirm),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # ----------------- subtasks -----------------
    def _subtask_row(self, task: dict, subtask: dict) -> ft.Control:
        done = subtask.get("done", False)
        pdf_url = subtask.get("pdf_url")

        return ft.Row(
            [
                ft.Checkbox(
                    label=subtask.get("title", ""),
                    value=done,
                    on_change=lambda e, t=task, s=subtask: self._toggle_subtask(t, s, e.control.value),
                ),
                ft.Row(
                    [
                        ft.OutlinedButton("Attach PDF", on_click=lambda e, t=task, s=subtask: self._attach_subtask_pdf(t, s), visible=(pdf_url is None)),
                        ft.OutlinedButton("Open PDF", on_click=lambda e, url=pdf_url: self.page.launch_url(url), visible=(pdf_url is not None)),
                        ft.OutlinedButton("Remove PDF", on_click=lambda e, t=task, s=subtask: self._remove_subtask_pdf(t, s), style=ft.ButtonStyle(color=ft.Colors.RED), visible=(pdf_url is not None)),
                    ],
                    spacing=4
                ),
                ft.IconButton(ft.Icons.DELETE_FOREVER, tooltip="Delete subtask", icon_color=ft.Colors.RED, on_click=lambda e, t=task, sid=subtask.get("id"): self._delete_subtask(t, sid)),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _add_subtask_dialog(self, task: dict):
        title_f = ft.TextField(label="Subtask title")

        def save(e):
            title = (title_f.value or "").strip()
            if not title:
                return
            subs = self._as_list(task.get("subtasks"))
            subs.append({"id": str(uuid.uuid4()), "title": title, "done": False})
            try:
                set_task_subtasks(task["id"], subs)
                dlg.open = False
                self.toast("➕ Subtask added")
                self.refresh()
            except Exception as ex:
                print("❌ add subtask:", repr(ex))
                self.toast(f"❌ Failed: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Add Subtask"),
            content=title_f,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton("Save", on_click=save),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _toggle_subtask(self, task: dict, subtask: dict, done: bool):
        subs = self._as_list(task.get("subtasks"))
        for s in subs:
            if s.get("id") == subtask.get("id"):
                s["done"] = done
        try:
            set_task_subtasks(task["id"], subs)
            self.refresh()
        except Exception as ex:
            print("❌ toggle subtask:", repr(ex))
            self.toast(f"❌ Failed: {ex}")

    def _delete_subtask(self, task: dict, subtask_id: str):
        subs = [s for s in self._as_list(task.get("subtasks")) if s.get("id") != subtask_id]
        try:
            set_task_subtasks(task["id"], subs)
            self.toast("🗑️ Subtask deleted")
            self.refresh()
        except Exception as ex:
            print("❌ delete subtask:", repr(ex))
            self.toast(f"❌ Failed: {ex}")

    # ----------------- assign -----------------
    def _assign_dialog(self, task: dict):
        if not self.users_map:
            return self.toast("⚠️ No users found")

        current_assignees = set(self._as_list(task.get("assignees")))
        checkboxes = []
        selected = set(current_assignees)

        for uid, label in self.users_map.items():
            cb = ft.Checkbox(label=label, value=(uid in current_assignees))
            def on_change(e, uid=uid):
                if e.control.value:
                    selected.add(uid)
                else:
                    selected.discard(uid)
            cb.on_change = on_change
            checkboxes.append(cb)

        dlg = ft.AlertDialog(
            title=ft.Text("Assign Task"),
            content=ft.Column(checkboxes, spacing=5),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton("Save", on_click=lambda e: self._save_assignees(task["id"], selected, dlg)),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _save_assignees(self, task_id, selected_set, dlg):
        try:
            assignees = list(selected_set)
            set_task_assignees(task_id, assignees)
            dlg.open = False
            self.toast("✅ Assigned")
            self.refresh()
        except Exception as ex:
            print("❌ assign failed:", repr(ex))
            self.toast(f"❌ Assign failed: {ex}")

    # ----------------- comments -----------------
    def _comments_dialog(self, task: dict):
        comments = self._as_list(task.get("comments"))
        new_comment = ft.TextField(hint_text="Write a comment...", multiline=True)

        list_col = ft.Column(
            [
                ft.Text(f"{c.get('author','')}: {c.get('text','')} ({c.get('timestamp','')})", size=12)
                for c in comments
            ],
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
        )

        def send(e):
            txt = (new_comment.value or "").strip()
            if not txt:
                return
            comments.append({
                "id": str(uuid.uuid4()),
                "author": self.user.get("email") or "user",
                "text": txt,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            try:
                set_task_comments(task["id"], comments)
                dlg.open = False
                self.toast("💬 Comment added")
                self.refresh()
            except Exception as ex:
                print("❌ comment:", repr(ex))
                self.toast(f"❌ Failed: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text(f"Comments: {task.get('title','')}"),
            content=ft.Column([list_col, ft.Divider(), new_comment], tight=True, height=400),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton("Send", on_click=send),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # ----------------- PDF Attach -----------------
    def _delete_pdf_from_storage(self, pdf_url: str):
        try:
            marker = f"/{PDF_BUCKET}/"
            if marker not in pdf_url:
                return
            storage_path = pdf_url.split(marker, 1)[1]
            self.supabase.storage.from_(PDF_BUCKET).remove([storage_path])
        except Exception as ex:
            print("⚠️ storage delete failed:", repr(ex))

    def _attach_pdf(self, task: dict):
        self._pending_pdf = {"task_id": task["id"], "subtask_id": None}
        self.file_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
        )

    def _attach_subtask_pdf(self, task: dict, subtask: dict):
        self._pending_pdf = {"task_id": task["id"], "subtask_id": subtask["id"]}
        self.file_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
        )

    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files or not self._pending_pdf:
            return

        f = e.files[0]
        task_id = self._pending_pdf["task_id"]
        subtask_id = self._pending_pdf["subtask_id"]

        storage_key = (
            f"{task_id}/subtask_{subtask_id}_{uuid.uuid4().hex}.pdf"
            if subtask_id
            else f"{task_id}/{uuid.uuid4().hex}.pdf"
        )

        # ✅ DESKTOP
        if getattr(f, "path", None):
            try:
                with open(f.path, "rb") as fp:
                    data = fp.read()

                if subtask_id:
                    self._upload_subtask_pdf_bytes(task_id, subtask_id, storage_key, data)
                else:
                    self._upload_pdf_bytes(task_id, storage_key, data)

                self._pending_pdf = None
                return

            except Exception as ex:
                self.toast(f"❌ Cannot read PDF: {ex}")
                return

        # ✅ WEB (upload to server first)
        try:
            upload_url = self.page.get_upload_url(f.name, 600)
            self.file_picker.upload(
                [ft.FilePickerUploadFile(f.name, upload_url)]
            )
            self.toast("⬆️ Uploading PDF...")
        except Exception as ex:
            self.toast(f"❌ Upload init failed: {ex}")

    def _on_file_upload(self, e: ft.FilePickerUploadEvent):
        if e.error or not self._pending_pdf:
            return

        if e.progress is not None and e.progress < 1:
            return

        filename = e.file_name
        local_path = os.path.join(UPLOAD_DIR, filename)

        if not os.path.exists(local_path):
            self.toast("⚠️ Uploaded file not found locally")
            return

        task_id = self._pending_pdf["task_id"]
        subtask_id = self._pending_pdf["subtask_id"]

        try:
            with open(local_path, "rb") as fp:
                data = fp.read()

            storage_key = (
                f"{task_id}/subtask_{subtask_id}_{uuid.uuid4().hex}.pdf"
                if subtask_id
                else f"{task_id}/{uuid.uuid4().hex}.pdf"
            )

            if subtask_id:
                self._upload_subtask_pdf_bytes(task_id, subtask_id, storage_key, data)
            else:
                self._upload_pdf_bytes(task_id, storage_key, data)

            os.remove(local_path)
            self._pending_pdf = None

        except Exception as ex:
            self.toast(f"❌ Upload finalize failed: {ex}")

    def _upload_pdf_bytes(self, task_id: str, storage_key: str, data: bytes):
        try:
            self.supabase.storage.from_(PDF_BUCKET).upload(
                storage_key,
                data,
                {"content-type": "application/pdf"}
            )
            url = self.supabase.storage.from_(PDF_BUCKET).get_public_url(storage_key)
            set_task_pdf(task_id, url, "closed")
            self.toast("✅ PDF uploaded, task closed")
            self.refresh()
        except Exception as ex:
            print("❌ upload pdf:", repr(ex))
            self.toast(f"❌ PDF upload failed: {ex}")

    def _upload_subtask_pdf_bytes(self, task_id: str, subtask_id: str, storage_key: str, data: bytes):
        try:
            self.supabase.storage.from_(PDF_BUCKET).upload(
                storage_key,
                data,
                {"content-type": "application/pdf"}
            )
            url = self.supabase.storage.from_(PDF_BUCKET).get_public_url(storage_key)

            task = fetch_task(task_id)
            subs = self._as_list(task.get("subtasks"))
            for s in subs:
                if s.get("id") == subtask_id:
                    s["pdf_url"] = url
            set_task_subtasks(task_id, subs)
            self.toast("✅ Subtask PDF uploaded")
            self.refresh()
        except Exception as ex:
            print("❌ upload subtask pdf:", repr(ex))
            self.toast(f"❌ PDF upload failed: {ex}")

    def _remove_pdf(self, task: dict):
        pdf_url = task.get("pdf_url")
        if pdf_url:
            self._delete_pdf_from_storage(pdf_url)
            set_task_pdf(task["id"], None, "open")
            self.toast("❌ PDF removed, task reopened")
            self.refresh()

    def _remove_subtask_pdf(self, task: dict, subtask: dict):
        pdf_url = subtask.get("pdf_url")
        if pdf_url:
            self._delete_pdf_from_storage(pdf_url)
            subs = self._as_list(task.get("subtasks"))
            for s in subs:
                if s.get("id") == subtask.get("id"):
                    s["pdf_url"] = None
            set_task_subtasks(task["id"], subs)
            self.toast("❌ Subtask PDF removed")
            self.refresh()

    # ----------------- logout -----------------
    def logout(self, e=None):
        sign_out()
        self.on_logout()
