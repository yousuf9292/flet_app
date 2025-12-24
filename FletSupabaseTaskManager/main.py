import flet as ft
from app.auth import restore_session_if_any, get_current_user
from pages.login import LoginPage
from pages.signup import SignupPage
from pages.dashboard import DashboardPage


def main(page: ft.Page):
    page.title = "Task Manager"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.snack_bar = ft.SnackBar(ft.Text(""))

    def go(route: str):
        page.go(route)

    def on_route_change(e: ft.RouteChangeEvent):
        page.views.clear()

        if page.route == "/signup":
            page.views.append(ft.View("/signup", [SignupPage(page, go_login=lambda: go("/login"))]))

        elif page.route == "/dashboard":
            if not get_current_user():
                go("/login")
                return
            page.views.append(ft.View("/dashboard", [DashboardPage(page, on_logout=lambda: go("/login"))]))

        else:
            page.views.append(
                ft.View(
                    "/login",
                    [
                        LoginPage(
                            page,
                            on_success=lambda user, session: go("/dashboard"),
                            go_signup=lambda: go("/signup"),
                        )
                    ],
                )
            )

        page.update()

    page.on_route_change = on_route_change

    # Restore session (web refresh friendly)
    if restore_session_if_any():
        page.go("/dashboard")
    else:
        page.go("/login")


# For desktop or browser
ft.app(target=main, view=ft.WEB_BROWSER)
