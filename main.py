print("Starting main.py...")
import flet as ft
from app.auth import restore_session_if_any, get_current_user
from pages.login import LoginPage
from pages.signup import SignupPage
from pages.dashboard import DashboardPage
from pages.task_table import TaskTablePage

import os
from dotenv import load_dotenv

load_dotenv()


def main(page: ft.Page):
    page.title = "Task Manager"
    page.theme_mode = ft.ThemeMode.LIGHT

    # Enable adaptive design features
    page.padding = 0
    page.spacing = 0

    def go(route: str):
        page.go(route)

    def on_route_change(e: ft.RouteChangeEvent):
        page.views.clear()

        # Responsive View Configuration
        # We use scroll=ft.ScrollMode.AUTO to ensure mobile users can scroll
        # if the keyboard or small screen clips the content.

        # -------- SIGNUP --------
        if page.route == "/signup":
            page.views.append(
                ft.View(
                    "/signup",
                    [SignupPage(page, go_login=lambda: go("/login"))],
                    padding=0,
                )
            )

        # -------- DASHBOARD --------
        elif page.route == "/dashboard":
            if not get_current_user():
                page.go("/login")
                return

            page.views.append(
                ft.View(
                    "/dashboard",
                    [
                        DashboardPage(
                            page,
                            on_logout=lambda: go("/login"),
                        )
                    ],
                    padding=0,
                    bgcolor=ft.Colors.BLUE_GREY_50,
                )
            )

        # -------- TASK TABLE --------
        elif page.route == "/table":
            if not get_current_user():
                page.go("/login")
                return

            page.views.append(
                ft.View(
                    "/table",
                    [
                        TaskTablePage(
                            page,
                            on_back=lambda: go("/dashboard"),
                        )
                    ],
                    padding=0,
                    bgcolor=ft.Colors.BLUE_GREY_50,
                )
            )

        # -------- LOGIN (default) --------
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
                    padding=0,
                    # Center login content on large screens
                    vertical_alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        page.update()

    # global resize handler (Optional: broadcast resize to the active view)
    def on_page_resize(e):
        # This forces a UI refresh across the app when the window
        # transitions between mobile/desktop widths.
        page.update()

    page.on_route_change = on_route_change
    page.on_resize = on_page_resize

    # Restore session (refresh-friendly)
    if restore_session_if_any():
        page.go("/dashboard")
    else:
        page.go("/login")


# Security and Upload Config
os.environ.setdefault("FLET_SECRET_KEY", "any-long-random-string-here")

# Run the app
ft.app(
    target=main,
    upload_dir="uploads",
    # Assets dir allows for custom icons/images if needed later
    assets_dir="assets"
)
