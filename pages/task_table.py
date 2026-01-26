# pages/task_table.py
import json
import pandas as pd
import flet as ft
import asyncio

from app.auth import get_current_user, get_supabase
from app.db_client import fetch_tasks_for_user, set_task_subtasks


class TaskTablePage(ft.Container):
    def __init__(self, page: ft.Page, on_back):
        super().__init__()
        self.page = page
        self.on_back = on_back

        # Layout
        self.expand = True
        self.padding = 16
        self.bgcolor = ft.Colors.BLUE_GREY_50

        self.supabase = get_supabase()
        self.user = get_current_user() or {}

        self.users_map = {}
        self._load_users()

        self._mounted = False

        # Responsive (window_width is more reliable on web/mobile)
        w = getattr(self.page, "window_width", None) or self.page.width or 1000
        self.is_mobile = w < 800

        # ---------- Stats ----------
        self.total_txt = ft.Text("0", color=ft.Colors.WHITE, size=22, weight="bold")
        self.open_txt = ft.Text("0", color=ft.Colors.WHITE, size=22, weight="bold")
        self.closed_txt = ft.Text("0", color=ft.Colors.WHITE, size=22, weight="bold")

        # ---------- Filters ----------
        self.status_filter = ft.Dropdown(
            label="Status",
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("open"),
                ft.dropdown.Option("closed"),
            ],
            value="All",
            width=160,
            on_change=lambda e: self.refresh_table(),
        )

        self.task_filter = ft.TextField(
            label="Search task or subtask...",
            expand=True,
            on_change=lambda e: self.refresh_table(),
        )

        # ---------- Table ----------
        self.table = ft.DataTable(
            column_spacing=20,
            heading_row_color=ft.Colors.GREY_100,
            columns=[
                ft.DataColumn(ft.Text("Task", weight="bold")),
                ft.DataColumn(ft.Text("Status", weight="bold")),
                ft.DataColumn(ft.Text("Assignees", weight="bold")),
                ft.DataColumn(ft.Text("Subtask", weight="bold")),
                ft.DataColumn(ft.Text("Progress", weight="bold")),
                ft.DataColumn(ft.Text("File", weight="bold")),
            ],
            rows=[],
        )

        # ---------- Mobile List ----------
        self.mobile_list = ft.ListView(spacing=10, padding=0, expand=True)

        # ---------- Desktop table wrapper (fixed constraints) ----------
        self.desktop_table_area = ft.Container(
            height=520,
            visible=not self.is_mobile,
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=1100,  # horizontal scroll area
                        content=self.table,
                    )
                ],
                scroll=ft.ScrollMode.ALWAYS,
            ),
        )

        # ---------- Mobile wrapper ----------
        self.mobile_list_area = ft.Container(
            height=520,
            visible=self.is_mobile,
            content=self.mobile_list,
        )

        # ---------- Page Body ----------
        self.body = ft.Column(expand=True, spacing=15)
        self.content = self.body

        self._build_layout()

    # ---------------- Lifecycle ----------------

    def did_mount(self):
        self._mounted = True

        # Defer one tick so web layout settles before drawing table/list
        try:
            self.page.run_task(self._after_mount)
        except Exception:
            self._sync_responsive()
            self.refresh_table()

    async def _after_mount(self):
        await asyncio.sleep(0)
        self._sync_responsive()
        self.refresh_table()

    # ---------------- Responsive ----------------

    def _sync_responsive(self):
        w = getattr(self.page, "window_width", None) or self.page.width or 1000
        self.is_mobile = w < 800
        self.desktop_table_area.visible = not self.is_mobile
        self.mobile_list_area.visible = self.is_mobile

    # ---------------- UI ----------------

    def _build_layout(self):
        self.body.controls = [
            # Header
            ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.on_back()),
                    ft.Text("Task Overview", size=20, weight="bold", expand=True),
                    ft.ElevatedButton("CSV", icon=ft.Icons.DOWNLOAD, on_click=self.export_csv),
                    ft.OutlinedButton("JSON", icon=ft.Icons.CODE, on_click=self.export_json),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),

            # Stats Cards
            ft.Row(
                [
                    self._stat_card("Total", self.total_txt, ft.Colors.BLUE_600),
                    self._stat_card("Open", self.open_txt, ft.Colors.GREEN_600),
                    self._stat_card("Closed", self.closed_txt, ft.Colors.RED_600),
                ],
                wrap=True,
                spacing=15,
            ),

            # Filters
            ft.Row([self.status_filter, self.task_filter], spacing=10),

            # Main Content Card
            ft.Container(
                expand=True,
                padding=15,
                bgcolor=ft.Colors.WHITE,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.GREY_300),
                content=ft.Column(
                    [
                        ft.Text("Task Records", size=16, weight="bold"),
                        self.desktop_table_area,
                        self.mobile_list_area,
                    ],
                    spacing=10,
                ),
            ),
        ]

    # ---------------- Data ----------------

    def refresh_table(self):
        if not self._mounted:
            return

        self._sync_responsive()

        tasks = fetch_tasks_for_user() or []
        status_f = (self.status_filter.value or "All").lower()
        search_f = (self.task_filter.value or "").lower()

        total = open_c = closed = 0
        rows = []
        cards = []

        for task in tasks:
            task_status = (task.get("status") or "open").lower()

            total += 1
            if task_status == "open":
                open_c += 1
            elif task_status == "closed":
                closed += 1

            if status_f != "all" and task_status != status_f:
                continue

            assignees = self._as_list(task.get("assignees"))
            assignee_names = ", ".join([self.users_map.get(uid, uid[:6]) for uid in assignees]) or "—"
            subtasks = self._as_list(task.get("subtasks")) or [{}]

            # overall task progress for mobile
            all_subs = self._as_list(task.get("subtasks")) or []
            tot_subs = len(all_subs)
            done_subs = sum(1 for s in all_subs if s.get("done"))
            task_progress = (done_subs / tot_subs) if tot_subs else 0.0
            progress_label = f"{done_subs}/{tot_subs}"

            for sub in subtasks:
                sub_title = sub.get("title", "—")

                if search_f and search_f not in f"{task.get('title', '')} {sub_title}".lower():
                    continue

                pdf_url = sub.get("pdf_url") or task.get("pdf_url")
                done = bool(sub.get("done"))

                # -------- Desktop row --------
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(task.get("title", ""), weight="bold")),
                            ft.DataCell(self._status_badge(task_status)),
                            ft.DataCell(ft.Text(assignee_names, size=12)),
                            ft.DataCell(ft.Text(sub_title)),
                            ft.DataCell(self._done_pill(done, task, sub)),
                            ft.DataCell(
                                ft.IconButton(
                                    icon=ft.Icons.PICTURE_AS_PDF,
                                    icon_color=ft.Colors.RED_600,
                                    on_click=lambda e, url=pdf_url: self.page.launch_url(url),
                                )
                                if pdf_url
                                else ft.Text("—")
                            ),
                        ]
                    )
                )

                # -------- Mobile card --------
                cards.append(
                    ft.Container(
                        padding=12,
                        border_radius=10,
                        border=ft.border.all(1, ft.Colors.GREY_200),
                        bgcolor=ft.Colors.WHITE,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(task.get("title", ""), weight="bold", expand=True),
                                        self._status_badge(task_status),
                                    ]
                                ),
                                ft.Text(f"Subtask: {sub_title}", size=13),

                                # ✅ Progress (same meaning as desktop column: Done/Pending pill for subtask)
                                self._done_pill(done, task, sub),

                                # ✅ Overall task progress bar
                                ft.Row(
                                    [
                                        ft.Text("Overall", size=11, color=ft.Colors.GREY_600),
                                        ft.Text(progress_label, size=11, color=ft.Colors.GREY_600),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.ProgressBar(value=task_progress),

                                ft.Row(
                                    [
                                        ft.Text(f"By: {assignee_names}", size=11, color=ft.Colors.GREY_600),
                                        ft.IconButton(
                                            ft.Icons.PICTURE_AS_PDF,
                                            icon_size=18,
                                            on_click=lambda e, url=pdf_url: self.page.launch_url(url),
                                        )
                                        if pdf_url
                                        else ft.Container(),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                            ],
                            spacing=6,
                        ),
                    )
                )

        self.total_txt.value = str(total)
        self.open_txt.value = str(open_c)
        self.closed_txt.value = str(closed)

        self.table.rows = rows
        self.mobile_list.controls = cards

        self.update()

    # ---------------- UI Helpers ----------------

    def _stat_card(self, title, value_control, color):
        return ft.Container(
            width=150,
            padding=15,
            border_radius=12,
            bgcolor=color,
            content=ft.Column(
                [
                    ft.Text(title.upper(), size=10, weight="bold", color=ft.Colors.WHITE70),
                    value_control,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
        )

    def _status_badge(self, status: str):
        color = ft.Colors.GREEN_600 if status == "open" else ft.Colors.RED_600
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            border_radius=15,
            bgcolor=color,
            content=ft.Text(status.capitalize(), size=10, color=ft.Colors.WHITE, weight="bold"),
        )

    def _done_pill(self, done: bool, task, sub):
        color = ft.Colors.BLUE_600 if done else ft.Colors.GREY_400
        return ft.GestureDetector(
            on_tap=lambda e: self._toggle_subtask_direct(task, sub, not done),
            content=ft.Container(
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                border_radius=15,
                bgcolor=color,
                content=ft.Text("Done" if done else "Pending", size=10, color=ft.Colors.WHITE, weight="bold"),
            ),
        )

    # ---------------- Logic ----------------

    def _toggle_subtask_direct(self, task, subtask, new_val):
        subs = self._as_list(task.get("subtasks"))
        for s in subs:
            if s.get("id") == subtask.get("id"):
                s["done"] = new_val
        set_task_subtasks(task["id"], subs)
        self.refresh_table()

    def _as_list(self, val):
        if isinstance(val, list):
            return val
        try:
            return json.loads(val) if val else []
        except Exception:
            return []

    def _load_users(self):
        try:
            res = self.supabase.table("profiles").select("id,full_name,email").execute()
            self.users_map = {
                u["id"]: (u.get("full_name") or u.get("email") or u["id"][:6])
                for u in (res.data or [])
            }
        except Exception:
            self.users_map = {}

    # ---------------- export ----------------

    def export_csv(self, e):
        tasks = fetch_tasks_for_user() or []
        data = []
        for t in tasks:
            for s in self._as_list(t.get("subtasks")):
                data.append(
                    {
                        "Task": t.get("title"),
                        "Status": t.get("status"),
                        "Subtask": s.get("title"),
                        "Done": s.get("done"),
                    }
                )
        df = pd.DataFrame(data)
        self.page.launch_url(f"data:text/csv;charset=utf-8,{df.to_csv(index=False)}")

    def export_json(self, e):
        tasks = fetch_tasks_for_user() or []
        self.page.launch_url(f"data:application/json;charset=utf-8,{json.dumps(tasks)}")
