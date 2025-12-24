import asyncio
import flet as ft
from app.auth import sign_in


class LoginPage(ft.Container):
    def __init__(self, page: ft.Page, on_success, go_signup):
        super().__init__()
        self.page = page
        self.on_success = on_success
        self.go_signup = go_signup
        if getattr(self.page, "snack_bar", None) is None:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(""), open=False)
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
        try:
            sb = ft.SnackBar(content=ft.Text(msg), open=True)

            # Newer Flet (recommended)
            if hasattr(self.page, "open"):
                self.page.open(sb)
            else:
                # Older fallback
                self.page.snack_bar = sb
                self.page.update()

            print("[LOGIN-TOAST]", msg)

        except Exception as ex:
            print("[LOGIN-TOAST-ERROR]", repr(ex), "MSG=", msg)

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
                print("[LOGIN] missing email/password")
                return

            user_data, session = await asyncio.to_thread(sign_in, email, password)

            if user_data:
                self._notify("✅ Logged in!")
                await asyncio.sleep(0)  # let UI render snackbar before navigation
                self.on_success(user_data, session)
            else:
                self._notify("❌ Invalid email or password.")
        except Exception as ex:
            self._notify(f"Login failed: {ex}")
            print("❌ login error:", repr(ex))
        finally:
            self.login_btn.disabled = False
            self.page.update()

