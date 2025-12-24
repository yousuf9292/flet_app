import flet as ft
from app.auth import get_current_user, sign_out
from app.db_client import add_task, fetch_tasks_for_user, delete_task


class DashboardPage(ft.Container):
    def __init__(self, page: ft.Page, on_logout):
        super().__init__()
        self.page = page
        self.on_logout = on_logout
        self.expand = True
        self.padding = 12
        self.bgcolor = ft.Colors.BLUE_GREY_50

        self.user = get_current_user() or {}

        self.title_f = ft.TextField(label="Task title", expand=True)
        self.desc_f = ft.TextField(label="Description", expand=True)

        self.add_btn = ft.ElevatedButton("➕ Add", on_click=self.add_clicked)
        self.refresh_btn = ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", on_click=lambda e: self.refresh())
        self.logout_btn = ft.OutlinedButton("Logout", on_click=self.logout)

        self.tasks_view = ft.ListView(expand=True, spacing=8, padding=8)

        header = ft.Row(
            [
                ft.Text(f"Welcome, {self.user.get('email','user')}", size=16, weight="bold", expand=True),
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

    def toast(self, msg):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg))
        self.page.snack_bar.open = True
        self.page.update()

    def refresh(self):
        self.tasks_view.controls.clear()
        tasks = fetch_tasks_for_user()
        if not tasks:
            self.tasks_view.controls.append(ft.Text("No tasks yet."))
        else:
            for t in tasks:
                self.tasks_view.controls.append(
                    ft.Row(
                        [
                            ft.Text(t.get("title", ""), expand=True),
                            ft.Text(t.get("description", "") or "", expand=True),
                            ft.IconButton(ft.Icons.DELETE, on_click=lambda e, tid=t["id"]: self.remove_task(tid)),
                        ]
                    )
                )
        self.page.update()

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

    def remove_task(self, task_id):
        try:
            delete_task(task_id)
            self.toast("🗑️ Deleted")
            self.refresh()
        except Exception as ex:
            print("❌ delete error:", repr(ex))
            self.toast(f"❌ Delete failed: {ex}")

    def logout(self, e):
        sign_out()
        self.on_logout()
