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
        self.expand = True
        self.padding = 10
        self.bgcolor = ft.Colors.BLUE_GREY_50

        self.supabase = get_supabase()
        self.user = get_current_user() or {}
        self.users_map = {}
        self._load_users()

        self._mounted = False
        self.is_mobile = True 

        # Stats
        self.total_txt = ft.Text("0", color=ft.Colors.WHITE, size=20, weight="bold")
        self.open_txt = ft.Text("0", color=ft.Colors.WHITE, size=20, weight="bold")
        self.closed_txt = ft.Text("0", color=ft.Colors.WHITE, size=20, weight="bold")

        # Filters
        self.status_filter = ft.Dropdown(
            label="Status",
            options=[ft.dropdown.Option("All"), ft.dropdown.Option("open"), ft.dropdown.Option("closed")],
            value="All",
            width=130,
            on_change=lambda e: self.refresh_table(),
        )
        self.task_filter = ft.TextField(
            label="Search...",
            expand=True,
            on_change=lambda e: self.refresh_table(),
        )

        # UI Components
        self.table = ft.DataTable(
            column_spacing=15,
            heading_row_color=ft.Colors.GREY_100,
            columns=[
                ft.DataColumn(ft.Text("Task")),
                ft.DataColumn(ft.Text("Status")),
                ft.DataColumn(ft.Text("Assignees")),
                ft.DataColumn(ft.Text("Subtask")),
                ft.DataColumn(ft.Text("Done")),
                ft.DataColumn(ft.Text("PDF")),
            ],
            rows=[],
        )

        self.mobile_list = ft.ListView(expand=True, spacing=10, padding=10)

        # Responsive Areas
        self.desktop_area = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            controls=[ft.Row([self.table], scroll=ft.ScrollMode.ALWAYS)],
            visible=False
        )
        self.mobile_area = ft.Column(expand=True, controls=[self.mobile_list], visible=True)

        self.body = ft.Column(expand=True, spacing=10)
        self.content = self.body
        self._build_layout()

    def did_mount(self):
        self._mounted = True
        # Logic to handle Android screen reporting
        self._sync_responsive()
        self.refresh_table()

    def _sync_responsive(self):
        w = self.page.width if self.page.width else 0
        self.is_mobile = w < 800
        self.desktop_area.visible = not self.is_mobile
        self.mobile_area.visible = self.is_mobile
        self.update()

    def _build_layout(self):
        self.body.controls = [
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.on_back()),
                ft.Text("Task Overview", size=18, weight="bold", expand=True),
            ]),
            ft.Row([
                self._stat_card("Total", self.total_txt, ft.Colors.BLUE_600),
                self._stat_card("Open", self.open_txt, ft.Colors.GREEN_600),
                self._stat_card("Closed", self.closed_txt, ft.Colors.RED_600),
            ], wrap=True, alignment="center"),
            ft.Row([self.status_filter, self.task_filter], spacing=5),
            ft.Container(
                expand=True,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                content=ft.Column([self.desktop_area, self.mobile_area], expand=True)
            ),
        ]

    def _open_pdf(self, url):
        """Fixed PDF opening for Mobile/Android"""
        if not url:
            return
        # Using web_browser_name="chrome" or similar helps on Android to trigger a viewer
        self.page.launch_url(url)

    def refresh_table(self):
        if not self._mounted: return
        tasks = fetch_tasks_for_user() or []
        st_f = (self.status_filter.value or "All").lower()
        sr_f = (self.task_filter.value or "").lower()

        rows, cards = [], []
        t_c = o_c = c_c = 0

        for t in tasks:
            status = (t.get("status") or "open").lower()
            t_c += 1
            if status == "open": o_c += 1
            elif status == "closed": c_c += 1

            if st_f != "all" and status != st_f: continue

            assignees = self._as_list(t.get("assignees"))
            assignee_names = ", ".join([self.users_map.get(u, u[:6]) for u in assignees]) or "Unassigned"
            
            subs = self._as_list(t.get("subtasks")) or [{}]
            for s in subs:
                sub_t = s.get("title", "—")
                if sr_f and sr_f not in f"{t.get('title','')} {sub_t}".lower(): continue

                p_url = s.get("pdf_url") or t.get("pdf_url")
                is_done = bool(s.get("done"))

                # Desktop Table Logic
                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(t.get("title",""), size=12)),
                    ft.DataCell(self._status_badge(status)),
                    ft.DataCell(ft.Text(assignee_names, size=11)),
                    ft.DataCell(ft.Text(sub_t, size=12)),
                    ft.DataCell(ft.Checkbox(value=is_done, scale=0.8, on_change=lambda e, t=t, s=s: self._toggle_subtask(t, s, e.control.value))),
                    ft.DataCell(ft.IconButton(ft.Icons.PICTURE_AS_PDF, icon_color="red", on_click=lambda e: self._open_pdf(p_url)) if p_url else ft.Text("-")),
                ]))

                # Mobile Card Logic (Full Data Parity)
                cards.append(
                    ft.Card(
                        content=ft.Container(
                            padding=12,
                            content=ft.Column([
                                ft.Row([ft.Text(t.get("title",""), weight="bold", size=14, expand=True), self._status_badge(status)]),
                                ft.Text(f"Subtask: {sub_t}", size=12, weight="w500"),
                                ft.Text(f"Assigned: {assignee_names}", size=11, color="bluegrey"),
                                ft.Divider(height=1, thickness=0.5),
                                ft.Row([
                                    ft.Checkbox(label="Done", value=is_done, on_change=lambda e, t=t, s=s: self._toggle_subtask(t, s, e.control.value)),
                                    ft.IconButton(ft.Icons.DOWNLOAD, icon_color="red", visible=bool(p_url), on_click=lambda e: self._open_pdf(p_url))
                                ], alignment="spaceBetween")
                            ], spacing=5)
                        )
                    )
                )

        self.total_txt.value, self.open_txt.value, self.closed_txt.value = str(t_c), str(o_c), str(c_c)
        self.table.rows = rows
        self.mobile_list.controls = cards
        self.update()

    def _stat_card(self, title, val, color):
        return ft.Container(width=100, padding=8, border_radius=8, bgcolor=color,
                            content=ft.Column([ft.Text(title, size=9, color="white"), val], horizontal_alignment="center", spacing=0))

    def _status_badge(self, s):
        return ft.Container(bgcolor=ft.Colors.GREEN_700 if s=="open" else ft.Colors.RED_700,
                            padding=ft.padding.symmetric(2, 6), border_radius=5,
                            content=ft.Text(s.upper(), color="white", size=9, weight="bold"))

    def _toggle_subtask(self, task, subtask, val):
        subs = self._as_list(task.get("subtasks"))
        for s in subs:
            if s.get("id") == subtask.get("id"): s["done"] = val
        set_task_subtasks(task["id"], subs)
        self.refresh_table()

    def _as_list(self, v):
        if isinstance(v, list): return v
        try: return json.loads(v) if v else []
        except: return []

    def _load_users(self):
        try:
            res = self.supabase.table("profiles").select("id,full_name").execute()
            self.users_map = {u["id"]: u["full_name"] for u in res.data}
        except: pass

    def export_csv(self, e):
        # CSV handling on Android requires permissions; usually opens in browser
        tasks = fetch_tasks_for_user() or []
        df = pd.DataFrame(tasks)
        csv_str = df.to_csv(index=False)
        self.page.launch_url(f"data:text/csv;charset=utf-8,{csv_str}")
