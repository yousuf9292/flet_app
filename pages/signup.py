import asyncio
import flet as ft
from app.auth import get_supabase, sign_up


class SignupPage(ft.Container):
    def __init__(self, page: ft.Page, go_login):
        super().__init__()
        self.page = page
        self.go_login = go_login
        if getattr(self.page, "snack_bar", None) is None:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(""), open=False)

        self.expand = True
        self.padding = 24
        self.alignment = ft.alignment.center
        self.bgcolor = ft.Colors.BLUE_GREY_50

        self.full_name = ft.TextField(label="Full name", autofocus=True)
        self.email = ft.TextField(label="Email")
        self.password = ft.TextField(label="Password", password=True, can_reveal_password=True)

        self.signup_btn = ft.ElevatedButton("✨ Create Account", on_click=self.signup)
        self.login_btn = ft.TextButton("Back to Login", on_click=lambda e: self.go_login())

        self.content = ft.Column(
            [
                ft.Text("Create an Account 👋", size=22, weight="bold"),
                self.full_name,
                self.email,
                self.password,
                self.signup_btn,
                ft.Row([ft.Text("Already have an account?"), self.login_btn],
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

            print("[SIGNUP-TOAST]", msg)

        except Exception as ex:
            print("[SIGNUP-TOAST-ERROR]", repr(ex), "MSG=", msg)

    def signup(self, e):
        self.page.run_task(self._signup_task)

    async def _signup_task(self):
        try:
            name = (self.full_name.value or "").strip()
            email = (self.email.value or "").strip()
            password = (self.password.value or "").strip()
            if not name or not email or not password:
                self._notify("⚠️ Full name, email and password required.")
                return

            res = await asyncio.to_thread(sign_up, email, password, name)
            if res and res.user:
                # Upsert profile for assignee display, etc.
                supabase = get_supabase()
                try:
                    await asyncio.to_thread(
                        lambda: supabase.table("profiles").upsert(
                            {"id": res.user.id, "email": email, "full_name": name}
                        ).execute()
                    )
                except Exception as ex:
                    print("⚠️ profiles upsert error:", ex)

                self._notify("✅ Account created! Please log in.")
                await asyncio.sleep(0)  # let UI paint snackbar before navigation
                self.go_login()

            else:
                self._notify("❌ Signup failed.")
        except Exception as ex:
            self._notify(f"Signup failed: {ex}")
            print("❌ signup error:", repr(ex))
