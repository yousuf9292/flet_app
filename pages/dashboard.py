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
        self.supabase = get_supabase()
        self.user = get_current_user() or {}

        # Responsive State
        self.is_mobile = self.page.width < 600

        # Users map
        self.users_map = {}
        self._load_users()

        # File picker
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        self.file_picker = ft.FilePicker(
            on_result=self._on_file_picked,
            on_upload=self._on_file_upload,
        )
        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)

        self._pending_pdf = None

        # Inputs
        self.title_f = ft.TextField(label="Task title", expand=True)
        self.desc_f = ft.TextField(label="Description", expand=True)
        self.tasks_view = ft.ListView(expand=True, spacing=10, padding=8)

        # Main Layout Container
        self.content_column = ft.Column(expand=True)
        self.content = self.content_column

        # Hook into resize event
        self.page.on_resize = self._handle_resize

        self.refresh()

    def _handle_resize(self, e):
        self.is_mobile = self.page.width < 600
        self.refresh()

    def _build_header(self):
        return ft.Row(
            [
                ft.Text(
                    f"Hi, {self.user.get('email', 'user').split('@')[0]}",
                    size=20, weight="bold", expand=True
                ),
                ft.IconButton(ft.Icons.TABLE_VIEW, on_click=lambda e: self.page.go("/table")),
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: self.refresh()),
                ft.IconButton(ft.Icons.LOGOUT, icon_color=ft.Colors.RED_400, on_click=self.logout),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _build_add_task_area(self):
        # On mobile, stack fields. On desktop, side-by-side.
        if self.is_mobile:
            return ft.Column([
                self.title_f,
                self.desc_f,
                ft.ElevatedButton("➕ Add Task", on_click=self.add_clicked, width=float("inf"))
            ], spacing=10)

        return ft.Row([
            self.title_f,
            self.desc_f,
            ft.ElevatedButton("➕ Add", on_click=self.add_clicked)
        ], spacing=10)

    def refresh(self):
        self._load_users()
        self.tasks_view.controls.clear()

        # Clear and rebuild main column for responsiveness
        self.content_column.controls = [
            self._build_header(),
            self._build_add_task_area(),
            ft.Divider(),
            self.tasks_view,
        ]

        tasks = fetch_tasks_for_user()
        if not tasks:
            self.tasks_view.controls.append(ft.Text("No tasks yet.", color=ft.Colors.GREY_500))
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

        # Actions buttons area (Responsive)
        actions_row = ft.Row(
            [
                ft.OutlinedButton("Subtask", icon=ft.Icons.ADD, on_click=lambda e: self._add_subtask_dialog(task)),
                ft.OutlinedButton("Assign", icon=ft.Icons.PERSON_ADD, on_click=lambda e: self._assign_dialog(task)),
                ft.OutlinedButton(f"Comments ({len(self._as_list(task.get('comments')))})", icon=ft.Icons.COMMENT,
                                  on_click=lambda e: self._comments_dialog(task)),
            ],
            wrap=True,
            spacing=5
        )

        pdf_section = ft.Row(wrap=True, spacing=5)
        if not pdf_url:
            pdf_section.controls.append(ft.ElevatedButton("Attach PDF & Close", icon=ft.Icons.UPLOAD_FILE,
                                                          on_click=lambda e: self._attach_pdf(task)))
        else:
            pdf_section.controls.extend([
                ft.TextButton("Open PDF", icon=ft.Icons.PICTURE_AS_PDF,
                              on_click=lambda e: self.page.launch_url(pdf_url)),
                ft.TextButton("Remove", icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED,
                              on_click=lambda e: self._remove_pdf(task))
            ])

        return ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column([
                    ft.Row([
                        ft.Text(task.get("title", ""), size=18, weight="bold", expand=True),
                        ft.IconButton(ft.Icons.EDIT, icon_size=20, on_click=lambda e: self._edit_task_dialog(task)),
                        ft.IconButton(ft.Icons.DELETE, icon_size=20, icon_color=ft.Colors.RED_400,
                                      on_click=lambda e: self._delete_confirm(task)),
                    ]),
                    ft.Text(task.get("description") or "No description", color=ft.Colors.GREY_700),

                    # Status and Assignee (Stacks on Mobile)
                    ft.ResponsiveRow([
                        ft.Column([
                            ft.Dropdown(
                                label="Status",
                                value=status,
                                options=[
                                    ft.dropdown.Option("open", "Open"),
                                    ft.dropdown.Option("in_progress", "In Progress"),
                                    ft.dropdown.Option("closed", "Closed"),
                                ],
                                on_change=lambda e: self._change_task_status(task, e.control.value),
                            )
                        ], col={"xs": 12, "sm": 5}),
                        ft.Column([
                            ft.Text(f"Assigned: {assignee_text}", size=12, color=ft.Colors.BLUE_GREY_400)
                        ], col={"xs": 12, "sm": 7},
                            alignment=ft.alignment.center_left if self.is_mobile else ft.alignment.center_right)
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

                    ft.Divider(height=10, thickness=1),
                    ft.Text("Subtasks", weight="bold", size=14),
                    ft.Column([self._subtask_row(task, s) for s in subtasks], spacing=2) if subtasks else ft.Text(
                        "None", size=12, italic=True),

                    ft.Divider(height=10, thickness=1),
                    actions_row,
                    pdf_section
                ], spacing=10)
            )
        )

    def _subtask_row(self, task: dict, subtask: dict) -> ft.Control:
        pdf_url = subtask.get("pdf_url")
        return ft.Row(
            [
                ft.Checkbox(
                    label=subtask.get("title", ""),
                    value=subtask.get("done", False),
                    expand=True,
                    on_change=lambda e: self._toggle_subtask(task, subtask, e.control.value),
                ),
                ft.Row([
                    ft.IconButton(ft.Icons.UPLOAD_FILE, icon_size=18, tooltip="Attach PDF",
                                  on_click=lambda e: self._attach_subtask_pdf(task, subtask), visible=not pdf_url),
                    ft.IconButton(ft.Icons.PICTURE_AS_PDF, icon_size=18, tooltip="View",
                                  on_click=lambda e: self.page.launch_url(pdf_url), visible=bool(pdf_url)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, icon_color=ft.Colors.RED_300,
                                  on_click=lambda e: self._remove_subtask_pdf(task, subtask), visible=bool(pdf_url)),
                    ft.IconButton(ft.Icons.CLOSE, icon_size=18, icon_color=ft.Colors.GREY_400,
                                  on_click=lambda e: self._delete_subtask(task, subtask["id"])),
                ], spacing=0)
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    # ... [Rest of the CRUD/Logic methods remain the same as your original code] ...
    # Ensure they use self.refresh() to trigger the UI rebuild

    def _as_list(self, val):
        if val is None: return []
        if isinstance(val, list): return val
        try:
            return json.loads(val) if val else []
        except:
            return []

    def _load_users(self):
        try:
            users = self.supabase.table("profiles").select("id,email,full_name").execute().data or []
            self.users_map = {u["id"]: (u.get("full_name") or u.get("email") or u["id"][:6]) for u in users if
                              u.get("id")}
        except:
            self.users_map = {}

    def toast(self, msg: str):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(msg), open=True)
        self.page.update()

    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def add_clicked(self, e):
        title = (self.title_f.value or "").strip()
        if not title: return self.toast("⚠️ Enter a title")
        if add_task(title, self.desc_f.value):
            self.title_f.value = "";
            self.desc_f.value = ""
            self.toast("✅ Added");
            self.refresh()

    def _change_task_status(self, task: dict, new_status: str):
        update_task(task["id"], {"status": new_status})
        self.refresh()

    def _edit_task_dialog(self, task: dict):
        t_f = ft.TextField(label="Title", value=task.get("title", ""))
        d_f = ft.TextField(label="Description", value=task.get("description", ""), multiline=True)

        def save(e):
            update_task(task["id"], {"title": t_f.value, "description": d_f.value})
            dlg.open = False;
            self.refresh()

        dlg = ft.AlertDialog(title=ft.Text("Edit"), content=ft.Column([t_f, d_f], tight=True),
                             actions=[ft.ElevatedButton("Save", on_click=save)])
        self.page.overlay.append(dlg);
        dlg.open = True;
        self.page.update()

    def _delete_confirm(self, task: dict):
        def confirm(e):
            delete_task(task["id"]);
            dlg.open = False;
            self.refresh()

        dlg = ft.AlertDialog(title=ft.Text("Delete?"),
                             actions=[ft.TextButton("No"), ft.ElevatedButton("Yes", on_click=confirm)])
        self.page.overlay.append(dlg);
        dlg.open = True;
        self.page.update()

    def _add_subtask_dialog(self, task: dict):
        t_f = ft.TextField(label="Subtask title")

        def save(e):
            subs = self._as_list(task.get("subtasks"))
            subs.append({"id": str(uuid.uuid4()), "title": t_f.value, "done": False})
            set_task_subtasks(task["id"], subs);
            dlg.open = False;
            self.refresh()

        dlg = ft.AlertDialog(title=ft.Text("Add Subtask"), content=t_f,
                             actions=[ft.ElevatedButton("Add", on_click=save)])
        self.page.overlay.append(dlg);
        dlg.open = True;
        self.page.update()

    def _toggle_subtask(self, task, subtask, done):
        subs = self._as_list(task.get("subtasks"))
        for s in subs:
            if s.get("id") == subtask.get("id"): s["done"] = done
        set_task_subtasks(task["id"], subs);
        self.page.update()

    def _delete_subtask(self, task, subtask_id):
        subs = [s for s in self._as_list(task.get("subtasks")) if s.get("id") != subtask_id]
        set_task_subtasks(task["id"], subs);
        self.refresh()

    def _assign_dialog(self, task: dict):
        current = set(self._as_list(task.get("assignees")))
        cbs = []
        for uid, label in self.users_map.items():
            cb = ft.Checkbox(label=label, value=(uid in current), data=uid)
            cbs.append(cb)

        def save(e):
            set_task_assignees(task["id"], [c.data for c in cbs if c.value])
            dlg.open = False;
            self.refresh()

        dlg = ft.AlertDialog(title=ft.Text("Assign"),
                             content=ft.Column(cbs, tight=True, scroll=ft.ScrollMode.AUTO, height=200),
                             actions=[ft.ElevatedButton("Save", on_click=save)])
        self.page.overlay.append(dlg);
        dlg.open = True;
        self.page.update()

    def _comments_dialog(self, task: dict):
        comments = self._as_list(task.get("comments"))
        new_c = ft.TextField(hint_text="Comment...", multiline=True)
        list_c = ft.Column([ft.Text(f"{c['author']}: {c['text']}", size=12) for c in comments],
                           scroll=ft.ScrollMode.AUTO, height=200)

        def send(e):
            comments.append({"author": self.user.get("email"), "text": new_c.value,
                             "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")})
            set_task_comments(task["id"], comments);
            dlg.open = False;
            self.refresh()

        dlg = ft.AlertDialog(title=ft.Text("Comments"), content=ft.Column([list_c, new_c], tight=True),
                             actions=[ft.ElevatedButton("Send", on_click=send)])
        self.page.overlay.append(dlg);
        dlg.open = True;
        self.page.update()

    def _attach_pdf(self, task):
        self._pending_pdf = {"task_id": task["id"], "subtask_id": None}
        self.file_picker.pick_files(allowed_extensions=["pdf"])

    def _attach_subtask_pdf(self, task, subtask):
        self._pending_pdf = {"task_id": task["id"], "subtask_id": subtask["id"]}
        self.file_picker.pick_files(allowed_extensions=["pdf"])

    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files or not self._pending_pdf:
            return

        f = e.files[0]
        tid, sid = self._pending_pdf["task_id"], self._pending_pdf["subtask_id"]

        if getattr(f, "path", None):  # Desktop
            with open(f.path, "rb") as fp:
                key = f"{tid}/{'sub_' + sid if sid else 'main'}_{uuid.uuid4().hex}.pdf"
                self._upload_wrapper(tid, sid, key, fp.read())
        else:  # Web / Mobile
            self.file_picker.upload([
                ft.FilePickerUploadFile(
                    f.name,
                    self.page.get_upload_url(f.name),
                )
            ])

    def _on_file_upload(self, e: ft.FilePickerUploadEvent):
        if e.error:
            self.toast("Upload failed")
            return

        if e.progress == 1 and e.file_content:
            tid = self._pending_pdf["task_id"]
            sid = self._pending_pdf["subtask_id"]

            key = f"{tid}/{'sub_' + sid if sid else 'main'}_{uuid.uuid4().hex}.pdf"

            self._upload_wrapper(
                tid,
                sid,
                key,
                e.file_content,  # ✅ THIS IS THE FIX
            )

    def _upload_wrapper(self, tid, sid, key, data):
        self.supabase.storage.from_(PDF_BUCKET).upload(key, data, {"content-type": "application/pdf"})
        url = self.supabase.storage.from_(PDF_BUCKET).get_public_url(key)
        if sid:
            task = fetch_task(tid);
            subs = self._as_list(task.get("subtasks"))
            for s in subs:
                if s["id"] == sid: s["pdf_url"] = url
            set_task_subtasks(tid, subs)
        else:
            set_task_pdf(tid, url, "closed")
        self.refresh()

    def _remove_pdf(self, task):
        update_task(task["id"], {"pdf_url": None});
        self.refresh()

    def _remove_subtask_pdf(self, task, subtask):
        subs = self._as_list(task.get("subtasks"))
        for s in subs:
            if s["id"] == subtask["id"]: s["pdf_url"] = None
        set_task_subtasks(task["id"], subs);
        self.refresh()

    def logout(self, e=None):
        sign_out();
        self.on_logout()
