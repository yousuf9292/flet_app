import json
import pandas as pd
import flet as ft
from urllib.parse import quote

from app.auth import get_current_user, get_supabase
from app.db_client import fetch_tasks_for_user, set_task_subtasks

class TaskTablePage(ft.Container):
    def __init__(self, page: ft.Page, on_back):
        super().__init__()
        self.page = page
        self.on_back = on_back
        
        # Container Styling
        self.expand = True
        self.padding = 10
        self.bgcolor = ft.Colors.BLUE_GREY_50

        # Data initialization
        self.supabase = get_supabase()
        self.user = get_current_user() or {}
        self.users_map = {}
        self._load_users()

        self._mounted = False
        self.is_mobile = True 

        # ---------- UI Controls ----------
        self.total_txt = ft.Text("0", color=ft.Colors.WHITE, size=22, weight="bold")
        self.open_txt = ft.Text("0", color=ft.Colors.WHITE, size=22, weight="bold")
        self.closed_txt = ft.Text("0", color=ft.Colors.WHITE, size=22, weight="bold")

        self.status_filter = ft.Dropdown(
            label="Filter Status",
            options=[ft.dropdown.Option("All"), ft.dropdown.Option("open"), ft.dropdown.Option("closed")],
            value="All",
            width=140,
            on_change=lambda e: self.refresh_table(),
        )

        self.task_filter = ft.TextField(
            label="Search tasks...",
            expand=True,
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda e: self.refresh_table(),
        )

        # ---------- Layout Components ----------
        self.table = ft.DataTable(
            column_spacing=20,
            heading_row_color=ft.Colors.GREY_100,
            columns=[
                ft.DataColumn(ft.Text("Task", weight="bold")),
                ft.DataColumn(ft.Text("Status", weight="bold")),
                ft.DataColumn(ft.Text("Assignees", weight="bold")),
                ft.DataColumn(ft.Text("Subtask", weight="bold")),
                ft.DataColumn(ft.Text("Done", weight="bold")),
                ft.DataColumn(ft.Text("PDF", weight="bold")),
            ],
            rows=[],
        )

        self.mobile_list = ft.ListView(expand=True, spacing=10, padding=5)

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
        self._sync_responsive()
        self.refresh_table()

    # ================= HELPERS =================

    def _sync_responsive(self):
        w = self.page.width if self.page.width else 0
        self.is_mobile = w < 850
        self.desktop_area.visible = not self.is_mobile
        self.mobile_area.visible = self.is_mobile
        self.update()

    def _as_list(self, v):
        if isinstance(v, list): return v
        try: return json.loads(v) if v else []
        except: return []

    def _load_users(self):
        try:
            res = self.supabase.table("profiles").select("id,full_name").execute()
            self.users_map = {u["id"]: u["full_name"] for u in res.data}
        except: pass

    def _status_badge(self, s):
        color = ft.Colors.GREEN_700 if s.lower() == "open" else ft.Colors.RED_700
        return ft.Container(
            bgcolor=color, padding=ft.padding.symmetric(2, 8), border_radius=5,
            content=ft.Text(s.upper(), color="white", size=10, weight="bold")
        )

    def _stat_card(self, title, val_control, color):
        return ft.Container(
            width=110, padding=10, border_radius=10, bgcolor=color,
            content=ft.Column([
                ft.Text(title, size=10, color="white", weight="w500"),
                val_control
            ], horizontal_alignment="center", spacing=0)
        )

    def _open_pdf(self, url):
        if not url: return
        self.page.launch_url(url, web_window_name="_blank")

    # ================= EXPORT LOGIC =================

    def export_csv(self, e):
        tasks = fetch_tasks_for_user() or []
        if not tasks: return

        flattened = []
        for t in tasks:
            subs = self._as_list(t.get("subtasks")) or [{"title": "General", "done": False}]
            names = ", ".join([self.users_map.get(u, u) for u in self._as_list(t.get("assignees"))])
            for s in subs:
                flattened.append({
                    "Task": t.get("title", ""),
                    "Status": t.get("status", ""),
                    "Assignees": names,
                    "Subtask": s.get("title", ""),
                    "Done": "Yes" if s.get("done") else "No",
                    "PDF": s.get("pdf_url") or t.get("pdf_url") or ""
                })

        df = pd.DataFrame(flattened)
        csv_data = quote(df.to_csv(index=False))
        self.page.launch_url(f"data:text/csv;charset=utf-8,{csv_data}", web_window_name="_blank")

    def export_json(self, e):
        tasks = fetch_tasks_for_user() or []
        json_data = quote(json.dumps(tasks, indent=4))
        self.page.launch_url(f"data:application/json;charset=utf-8,{json_data}", web_window_name="_blank")

    # ================= TABLE LOGIC =================

    def _toggle_subtask(self, task, subtask, val):
        subs = self._as_list(task.get("subtasks"))
        if not subs: return
        for s in subs:
            if s.get("id") == subtask.get("id"): s["done"] = val
        set_task_subtasks(task["id"], subs)
        self.refresh_table()

    def refresh_table(self):
        if not self._mounted: return
        
        tasks = fetch_tasks_for_user() or []
        st_filter = (self.status_filter.value or "All").lower()
        search_term = (self.task_filter.value or "").lower()

        rows, cards = [], []
        t_count = o_count = c_count = 0

        for t in tasks:
            status = (t.get("status") or "open").lower()
            t_count += 1
            if status == "open": o_count += 1
            elif status == "closed": c_count += 1

            if st_filter != "all" and status != st_filter: continue

            assignees = self._as_list(t.get("assignees"))
            names = ", ".join([self.users_map.get(u, "User") for u in assignees]) or "No Assignee"
            
            subs = self._as_list(t.get("subtasks")) or [{"title": "Main Task", "done": False, "id": "default"}]

            for s in subs:
                sub_title = s.get("title", "—")
                if search_term and search_term not in f"{t.get('title','')} {sub_title}".lower(): continue

                # KEY FIX: Subtask URL || Task URL (Desktop)
                final_url = s.get("pdf_url") or t.get("pdf_url")
                done_status = bool(s.get("done"))

                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(t.get("title",""), size=12, weight="bold")),
                    ft.DataCell(self._status_badge(status)),
                    ft.DataCell(ft.Text(names, size=11)),
                    ft.DataCell(ft.Text(sub_title, size=12)),
                    ft.DataCell(ft.Checkbox(value=done_status, scale=0.8, on_change=lambda e, tk=t, sk=s: self._toggle_subtask(tk, sk, e.control.value))),
                    ft.DataCell(ft.IconButton(ft.Icons.PICTURE_AS_PDF, icon_color="red", on_click=lambda e: self._open_pdf(final_url)) if final_url else ft.Text("-")),
                ]))

                cards.append(ft.Card(elevation=2, content=ft.Container(padding=12, content=ft.Column([
                    ft.Row([ft.Text(t.get("title",""), weight="bold", expand=True), self._status_badge(status)]),
                    ft.Text(f"Subtask: {sub_title}", size=12),
                    ft.Text(f"Assigned: {names}", size=11, color=ft.Colors.BLUE_GREY_400),
                    ft.Divider(height=1, thickness=0.5),
                    ft.Row([
                        ft.Checkbox(label="Done", value=done_status, on_change=lambda e, tk=t, sk=s: self._toggle_subtask(tk, sk, e.control.value)),
                        ft.IconButton(ft.Icons.OPEN_IN_NEW, icon_color="blue", visible=bool(final_url), on_click=lambda e: self._open_pdf(final_url))
                    ], alignment="spaceBetween")
                ], spacing=5))))

        self.total_txt.value, self.open_txt.value, self.closed_txt.value = str(t_count), str(o_count), str(c_count)
        self.table.rows = rows
        self.mobile_list.controls = cards
        self.update()

    def _build_layout(self):
        self.body.controls = [
            ft.Row([
                ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.on_back()),
                ft.Text("Audit & Reports", size=20, weight="bold", expand=True),
                ft.PopupMenuButton(items=[
                    ft.PopupMenuItem(text="Export CSV", icon=ft.Icons.DESCRIPTION, on_click=self.export_csv),
                    ft.PopupMenuItem(text="Export JSON", icon=ft.Icons.CODE, on_click=self.export_json),
                ]),
                ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: self.refresh_table()),
            ]),
            ft.Row([
                self._stat_card("TOTAL", self.total_txt, ft.Colors.BLUE_700),
                self._stat_card("OPEN", self.open_txt, ft.Colors.GREEN_700),
                self._stat_card("CLOSED", self.closed_txt, ft.Colors.RED_700),
            ], alignment="center", wrap=True),
            ft.Row([self.status_filter, self.task_filter]),
            ft.Container(
                expand=True, bgcolor=ft.Colors.WHITE, border_radius=12, padding=5,
                content=ft.Column([self.desktop_area, self.mobile_area], expand=True)
            ),
        ]
