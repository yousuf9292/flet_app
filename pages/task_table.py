import json
import pandas as pd
import io
import flet as ft
from app.auth import get_current_user, get_supabase
from app.db_client import fetch_tasks_for_user


class TaskTablePage(ft.Container):
    def __init__(self, page: ft.Page, on_back):
        super().__init__()
        self.page = page
        self.on_back = on_back
        self.expand = True
        self.padding = 16
        self.bgcolor = ft.Colors.BLUE_GREY_50

        self.supabase = get_supabase()
        self.user = get_current_user() or {}

        # Responsive State
        self.is_mobile = self.page.width < 700

        self.users_map = {}
        self._load_users()

        # ---------- stats controls ----------
        self.total_txt = ft.Text("0")
        self.open_txt = ft.Text("0")
        self.closed_txt = ft.Text("0")

        # ---------- filter controls ----------
        self.status_filter = ft.Dropdown(
            label="Status",
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("open"),
                ft.dropdown.Option("closed"),
            ],
            value="All",
            expand=1 if self.is_mobile else False,
            width=None if self.is_mobile else 160,
            on_change=lambda e: self.refresh_table(),
        )

        self.task_filter = ft.TextField(
            label="Search task / subtask",
            expand=2,
            on_change=lambda e: self.refresh_table(),
        )

        # ---------- table ----------
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
        )

        # Main Column to hold all responsive parts
        self.main_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
        self.content = self.main_content

        # Listen for window resize to toggle layout
        self.page.on_resize = self._on_resize

        self.refresh_table()

    def _on_resize(self, e):
        new_mobile_state = self.page.width < 700
        if new_mobile_state != self.is_mobile:
            self.is_mobile = new_mobile_state
            # Update UI components that depend on width
            self.status_filter.expand = 1 if self.is_mobile else False
            self.status_filter.width = None if self.is_mobile else 160
            self.refresh_table()

    def _build_header(self):
        # Stacks title and buttons on mobile
        title_row = ft.Row(
            [
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.on_back()),
                ft.Text("Task Overview", size=20, weight="bold", expand=True),
            ]
        )

        button_row = ft.Row(
            [
                ft.ElevatedButton("CSV", icon=ft.Icons.DOWNLOAD, on_click=self.export_csv),
                ft.OutlinedButton("JSON", icon=ft.Icons.CODE, on_click=self.export_json),
            ],
            alignment=ft.MainAxisAlignment.END if not self.is_mobile else ft.MainAxisAlignment.START
        )

        if self.is_mobile:
            return ft.Column([title_row, button_row], spacing=10)
        return ft.Row([title_row, button_row], alignment="spaceBetween")

    def _build_stats_row(self):
        # Stats stack vertically on very small screens or use wrap
        return ft.Row(
            spacing=10,
            wrap=True,
            controls=[
                self._stat_card("Total", self.total_txt, ft.Colors.BLUE_600),
                self._stat_card("Open", self.open_txt, ft.Colors.GREEN_600),
                self._stat_card("Closed", self.closed_txt, ft.Colors.RED_600),
            ],
        )

    def refresh_table(self):
        self.table.rows.clear()

        # Re-build layout controls to reflect current is_mobile state
        self.main_content.controls = [
            self._build_header(),
            self._build_stats_row(),
            ft.Row([self.status_filter, self.task_filter], wrap=self.is_mobile),
            ft.Container(
                padding=12,
                border_radius=12,
                bgcolor=ft.Colors.WHITE,
                border=ft.border.all(1, ft.Colors.GREY_300),
                content=ft.Column(
                    controls=[
                        ft.Text("Tasks", size=16, weight="bold"),
                        # Horizontal scroll for the table on mobile
                        ft.Row([self.table], scroll=ft.ScrollMode.ALWAYS)
                    ]
                )
            )
        ]

        tasks = fetch_tasks_for_user()
        status_f = self.status_filter.value.lower()
        search_f = (self.task_filter.value or "").lower()

        total = open_c = closed = 0

        for task in tasks:
            task_status = (task.get("status") or "open").lower()
            total += 1
            if task_status == "open": open_c += 1
            if task_status == "closed": closed += 1

            if status_f != "all" and task_status != status_f:
                continue

            assignees = self._as_list(task.get("assignees"))
            assignee_names = ", ".join([self.users_map.get(uid, uid[:6]) for uid in assignees]) or "—"
            subtasks = self._as_list(task.get("subtasks")) or [{}]

            for sub in subtasks:
                sub_title = sub.get("title", "—")
                if search_f and search_f not in f"{task.get('title', '')} {sub_title}".lower():
                    continue

                self.table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(task.get("title", ""), weight="bold")),
                            ft.DataCell(self._status_badge(task_status)),
                            ft.DataCell(ft.Text(assignee_names)),
                            ft.DataCell(ft.Text(sub_title)),
                            ft.DataCell(self._done_pill(sub.get("done"))),
                            ft.DataCell(
                                ft.IconButton(
                                    icon=ft.Icons.PICTURE_AS_PDF,
                                    icon_color=ft.Colors.RED_600,
                                    on_click=lambda e,
                                                    url=sub.get("pdf_url") or task.get("pdf_url"): self.page.launch_url(
                                        url),
                                ) if (sub.get("pdf_url") or task.get("pdf_url")) else ft.Text("—")
                            ),
                        ],
                    )
                )

        self.total_txt.value = str(total)
        self.open_txt.value = str(open_c)
        self.closed_txt.value = str(closed)
        self.page.update()

    # ---------------- UI helpers ----------------

    def _stat_card(self, title, value_control, color):
        # Make cards narrower on mobile
        return ft.Container(
            width=140 if self.is_mobile else 160,
            padding=12,
            border_radius=12,
            bgcolor=color,
            content=ft.Column(
                horizontal_alignment="center",
                spacing=4,
                controls=[
                    ft.Text(title.upper(), size=10, weight="bold", color=ft.Colors.WHITE70),
                    value_control,
                ],
            ),
        )

    def _status_badge(self, status: str):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=2),
            border_radius=20,
            bgcolor=ft.Colors.GREEN_600 if status == "open" else ft.Colors.RED_600,
            content=ft.Text(status.capitalize(), size=11, color=ft.Colors.WHITE, weight="bold"),
        )

    def _done_pill(self, done: bool):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=2),
            border_radius=20,
            bgcolor=ft.Colors.GREEN_600 if done else ft.Colors.GREY_600,
            content=ft.Text("Done" if done else "Pending", size=11, color=ft.Colors.WHITE, weight="bold"),
        )

    # ---------------- Data & Export helpers ----------------
    def _as_list(self, val):
        if isinstance(val, list): return val
        try:
            return json.loads(val) if isinstance(val, str) else []
        except:
            return []

    def _load_users(self):
        try:
            users = self.supabase.table("profiles").select("id,email,full_name").execute().data or []
            self.users_map = {u["id"]: (u.get("full_name") or u.get("email")) for u in users}
        except:
            self.users_map = {}

    def export_csv(self, e):
        tasks_data = []
        tasks = fetch_tasks_for_user()
        for task in tasks:
            for sub in (self._as_list(task.get("subtasks")) or [{}]):
                tasks_data.append({
                    "Task": task.get("title"),
                    "Status": task.get("status"),
                    "Subtask": sub.get("title", "—"),
                    "Done": "Yes" if sub.get("done") else "No"
                })
        df = pd.DataFrame(tasks_data)
        csv_str = df.to_csv(index=False)
        self.page.launch_url(f"data:text/csv;charset=utf-8,{csv_str}")

    def export_json(self, e):
        tasks = fetch_tasks_for_user()
        self.page.launch_url(f"data:application/json;charset=utf-8,{json.dumps(tasks)}")
