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

        self.supabase = get_supabase()
        self.user = get_current_user() or {}

        self.users_map = {}
        self._load_users()

        # ---------- stats ----------
        self.total_txt = ft.Text("0")
        self.open_txt = ft.Text("0")
        self.closed_txt = ft.Text("0")

        # ---------- filters ----------
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
            label="Search task / subtask",
            expand=True,
            on_change=lambda e: self.refresh_table(),
        )

        # ---------- table ----------
        self.table = ft.DataTable(
            expand=True,
            column_spacing=26,
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

        # ---------- layout ----------
        self.content = ft.Column(
            spacing=16,
            expand=True,
            controls=[
                # Header
                ft.Row(
                    alignment="spaceBetween",
                    controls=[
                        ft.Row(
                            controls=[
                                ft.IconButton(
                                    ft.Icons.ARROW_BACK,
                                    tooltip="Back",
                                    on_click=lambda e: self.on_back(),
                                ),
                                ft.Text(
                                    "Task & Subtask Overview",
                                    size=20,
                                    weight="bold",
                                ),
                            ]
                        ),
                        ft.Row(
                            controls=[
                                ft.ElevatedButton(
                                    "Export CSV",
                                    icon=ft.Icons.DOWNLOAD,
                                    on_click=self.export_csv,
                                ),
                                ft.OutlinedButton(
                                    "Export JSON",
                                    icon=ft.Icons.CODE,
                                    on_click=self.export_json,
                                ),
                            ]
                        ),
                    ],
                ),

                # Stats cards
                ft.Row(
                    spacing=16,
                    controls=[
                        self._stat_card("Total", self.total_txt, ft.Colors.BLUE_600),
                        self._stat_card("Open", self.open_txt, ft.Colors.GREEN_600),
                        self._stat_card("Closed", self.closed_txt, ft.Colors.RED_600),
                    ],
                ),

                # Filters
                ft.Row([self.status_filter, self.task_filter]),

                # Table container
                ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=ft.Colors.WHITE,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Text("Tasks", size=16, weight="bold"),
                            self.table,
                        ],
                    ),
                ),
            ],
        )

        self.refresh_table()

    # ---------------- UI helpers ----------------

    def _stat_card(self, title, value_control, color):
        value_control.size = 26
        value_control.weight = "bold"
        value_control.color = ft.Colors.WHITE

        return ft.Container(
            width=160,
            padding=16,
            border_radius=12,
            bgcolor=color,
            content=ft.Column(
                horizontal_alignment="center",
                spacing=6,
                controls=[
                    ft.Text(
                        title.upper(),
                        size=11,
                        weight="bold",
                        color=ft.Colors.WHITE70,
                    ),
                    value_control,
                ],
            ),
        )

    def _status_badge(self, status: str):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            border_radius=20,
            bgcolor=ft.Colors.GREEN_600 if status == "open" else ft.Colors.RED_600,
            content=ft.Text(
                status.capitalize(),
                size=12,
                weight="bold",
                color=ft.Colors.WHITE,
            ),
        )

    def _done_pill(self, done: bool):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=4),
            border_radius=20,
            bgcolor=ft.Colors.GREEN_600 if done else ft.Colors.GREY_600,
            content=ft.Text(
                "Done" if done else "Pending",
                size=12,
                weight="bold",
                color=ft.Colors.WHITE,
            ),
        )

    # ---------------- data helpers ----------------

    def _as_list(self, val):
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return []
        return []

    def _load_users(self):
        try:
            users = (
                self.supabase.table("profiles")
                .select("id,email,full_name")
                .execute()
                .data
                or []
            )
            self.users_map = {
                u["id"]: (u.get("full_name") or u.get("email"))
                for u in users
            }
        except Exception:
            self.users_map = {}

    # ---------------- table logic ----------------

    def refresh_table(self):
        self.table.rows.clear()

        tasks = fetch_tasks_for_user()
        status_f = self.status_filter.value.lower()
        search_f = (self.task_filter.value or "").lower()

        total = open_c = closed = 0

        for task in tasks:
            task_status = (task.get("status") or "open").lower()
            total += 1
            open_c += task_status == "open"
            closed += task_status == "closed"

            if status_f != "all" and task_status != status_f:
                continue

            assignees = self._as_list(task.get("assignees"))
            assignee_names = ", ".join(
                self.users_map.get(uid, uid[:6]) for uid in assignees
            ) or "—"

            subtasks = self._as_list(task.get("subtasks")) or [{}]

            for sub in subtasks:
                sub_title = sub.get("title", "—")
                combined = f"{task.get('title','')} {sub_title}".lower()

                if search_f and search_f not in combined:
                    continue

                row_index = len(self.table.rows)
                row_bg = ft.Colors.WHITE if row_index % 2 == 0 else ft.Colors.GREY_50

                self.table.rows.append(
                    ft.DataRow(
                        color=row_bg,
                        cells=[
                            ft.DataCell(
                                ft.Text(
                                    task.get("title", ""),
                                    weight="bold",
                                    color=ft.Colors.BLACK,
                                )
                            ),
                            ft.DataCell(self._status_badge(task_status)),
                            ft.DataCell(ft.Text(assignee_names)),
                            ft.DataCell(ft.Text(sub_title)),
                            ft.DataCell(self._done_pill(sub.get("done"))),
                            ft.DataCell(
                                ft.IconButton(
                                    icon=ft.Icons.PICTURE_AS_PDF,
                                    icon_color=ft.Colors.RED_600,
                                    tooltip="Open PDF",
                                    on_click=lambda e, url=sub.get("pdf_url")
                                    or task.get("pdf_url"): self.page.launch_url(url),
                                )
                                if (sub.get("pdf_url") or task.get("pdf_url"))
                                else ft.Text("—")
                            ),
                        ],
                    )
                )

        self.total_txt.value = str(total)
        self.open_txt.value = str(open_c)
        self.closed_txt.value = str(closed)

        self.page.update()

    # ---------------- export (still browser-based) ----------------

    def export_csv(self, e):
        # Use the actual task/subtask data
        tasks_data = []

        tasks = fetch_tasks_for_user()
        for task in tasks:
            task_status = (task.get("status") or "open").capitalize()
            assignees = ", ".join(
                self.users_map.get(uid, uid[:6]) for uid in self._as_list(task.get("assignees"))
            ) or "—"
            subtasks = self._as_list(task.get("subtasks")) or [{}]

            for sub in subtasks:
                tasks_data.append({
                    "Task": task.get("title", ""),
                    "Status": task_status,
                    "Assignees": assignees,
                    "Subtask": sub.get("title", "—"),
                    "Done": "Yes" if sub.get("done") else "No",
                })

        # Create CSV
        output = io.StringIO()
        df = pd.DataFrame(tasks_data)
        df.to_csv(output, index=False)
        self.page.launch_url(
            "data:text/csv;charset=utf-8," + output.getvalue()
        )

    def export_excel(self, e):
        # Export to Excel
        tasks_data = []

        tasks = fetch_tasks_for_user()
        for task in tasks:
            task_status = (task.get("status") or "open").capitalize()
            assignees = ", ".join(
                self.users_map.get(uid, uid[:6]) for uid in self._as_list(task.get("assignees"))
            ) or "—"
            subtasks = self._as_list(task.get("subtasks")) or [{}]

            for sub in subtasks:
                tasks_data.append({
                    "Task": task.get("title", ""),
                    "Status": task_status,
                    "Assignees": assignees,
                    "Subtask": sub.get("title", "—"),
                    "Done": "Yes" if sub.get("done") else "No",
                })

        # Create Excel file in-memory
        output = io.BytesIO()
        df = pd.DataFrame(tasks_data)
        df.to_excel(output, index=False, engine="openpyxl")
        excel_data = output.getvalue()
        b64_data = ft.base64.b64encode(excel_data).decode()

        self.page.launch_url(
            f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_data}"
        )

    def export_json(self, e):
        # Directly export tasks from DB
        tasks = fetch_tasks_for_user()
        self.page.launch_url(
            "data:application/json;charset=utf-8," +
            json.dumps(tasks, indent=2)
        )