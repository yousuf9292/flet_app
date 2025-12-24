import asyncio
import flet as ft
from app.auth import sign_in


class LoginPage(ft.Container):
    def __init__(self, page: ft.Page, on_success, go_signup):
        super().__init__()
        self.page = page
        self.on_success = on_success
        self.go_signup = go_signup

        self.expand = True
        self.padding = 24
        self.alignment = ft.alignment.center
        self.bgcolor = ft.Colors.BLUE_GREY_50

        self.email = ft.TextField(label="Email", autofocus=True)
        self.password = ft.TextField(label="Password", password=True, can_reveal_password=True)

        self.login_btn = ft.ElevatedButton("🔐 Login", on_click=self.login)
        self.signup_btn = ft.TextButton("Create an account", on_click=lambda e: self.go_signup())

        self.content = ft.Column(
            [
                ft.Text("Welcome Back 👋", size=22, weight="bold"),
                self.email,
                self.password,
                self.login_btn,
                ft.Row([ft.Text("Don't have an account?"), self.signup_btn],
                       alignment=ft.MainAxisAlignment.CENTER),
            ],
            width=360,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=12,
        )

    def _notify(self, msg: str):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg))
        self.page.snack_bar.open = True
        self.page.update()

    def login(self, e):
        self.page.run_task(self._login_task)

    async def _login_task(self):
        self.login_btn.disabled = True
        self.page.update()
        try:
            email = (self.email.value or "").strip()
            password = (self.password.value or "").strip()
            if not email or not password:
                self._notify("⚠️ Please fill both fields.")
                return

            # Run blocking supabase call in a thread (safer for --web)
            user_data, session = await asyncio.to_thread(sign_in, email, password)
            if user_data:
                self._notify("✅ Logged in!")
                self.on_success(user_data, session)
            else:
                self._notify("❌ Invalid email or password.")
        except Exception as ex:
            self._notify(f"Login failed: {ex}")
            print("❌ login error:", repr(ex))
        finally:
            self.login_btn.disabled = False
            self.page.update()
