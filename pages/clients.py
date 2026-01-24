import flet as ft
from app.db_client import fetch_clients, add_client, update_client, delete_client


class ClientsPage(ft.Container):
    def __init__(self, page: ft.Page, on_back):
        super().__init__()
        self.page = page
        self.on_back = on_back
        self.expand = True
        self.padding = 12
        self.bgcolor = ft.Colors.BLUE_GREY_50

        self.is_mobile = (getattr(self.page, "window_width", None) or self.page.width or 1000) < 700
        self.page.on_resize = self._on_resize

        # state
        self.editing_client_id = None
        self.clients = []

        # search
        self.search = ft.TextField(
            hint_text="Search client (branch, phone, email, city)...",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=12,
            on_change=lambda e: self._render_list(),
        )

        # list
        self.clients_list = ft.ListView(expand=True, spacing=10, padding=0)

        # add button
        self.add_btn = ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            text="Add",
            on_click=lambda e: self._open_form(mode="add"),
        )

        # Form fields (reused for add/edit)
        self.phone = ft.TextField(label="Phone", border_radius=12)
        self.email = ft.TextField(label="Email", border_radius=12)
        self.gst = ft.TextField(label="GST", border_radius=12)
        self.ntn = ft.TextField(label="NTN", border_radius=12)
        self.nic = ft.TextField(label="NIC", border_radius=12)
        self.city = ft.TextField(label="City", border_radius=12)
        self.area = ft.TextField(label="Area", border_radius=12)
        self.branch_name = ft.TextField(label="Branch name", border_radius=12)
        self.branch_address = ft.TextField(label="Branch address", multiline=True, min_lines=2, border_radius=12)
        self.billing_address = ft.TextField(label="Billing address", multiline=True, min_lines=2, border_radius=12)

        # container page content
        self.content = ft.Stack(
            expand=True,
            controls=[
                ft.Column(
                    expand=True,
                    spacing=12,
                    controls=[
                        self._header(),
                        self.search,
                        self.clients_list,
                    ],
                ),
                # FAB on bottom-right
                ft.Container(
                    content=self.add_btn,
                    alignment=ft.alignment.bottom_right,
                    padding=12,
                )
            ],
        )

        self.refresh()

    # ---------------- responsive ----------------
    def _on_resize(self, e):
        self.is_mobile = (getattr(self.page, "window_width", None) or self.page.width or 1000) < 700

    # ---------------- UI ----------------
    def _header(self):
        return ft.Container(
            padding=12,
            border_radius=16,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_200),
            content=ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.on_back()),
                    ft.Text("Clients", size=18, weight="bold", expand=True),
                    ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", on_click=lambda e: self.refresh()),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

    # ---------------- data ----------------
    def refresh(self):
        self.clients = fetch_clients() or []
        self._render_list()
        self.page.update()

    def _render_list(self):
        q = (self.search.value or "").strip().lower()

        def match(c):
            blob = " ".join([
                str(c.get("branch_name") or ""),
                str(c.get("person_phone") or ""),
                str(c.get("person_email") or ""),
                str(c.get("city") or ""),
                str(c.get("area") or ""),
                str(c.get("gst") or ""),
                str(c.get("ntn") or ""),
            ]).lower()
            return q in blob

        items = [c for c in self.clients if match(c)] if q else list(self.clients)

        self.clients_list.controls.clear()
        if not items:
            self.clients_list.controls.append(
                ft.Container(
                    padding=16,
                    border_radius=16,
                    bgcolor=ft.Colors.WHITE,
                    border=ft.border.all(1, ft.Colors.GREY_200),
                    content=ft.Text("No clients found.", color=ft.Colors.GREY_600),
                )
            )
        else:
            for c in items:
                self.clients_list.controls.append(self._client_card(c))

        self.clients_list.update() if getattr(self.clients_list, "page", None) else None

    # ---------------- cards ----------------
    def _client_card(self, c: dict):
        title = c.get("branch_name") or c.get("person_email") or "Client"
        phone = c.get("person_phone") or "—"
        email = c.get("person_email") or "—"
        loc = f"{(c.get('city') or '').strip()} {(c.get('area') or '').strip()}".strip() or "—"
        gst = c.get("gst") or "—"
        ntn = c.get("ntn") or "—"

        return ft.Container(
            padding=12,
            border_radius=16,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_200),
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        [
                            ft.Text(title, weight="bold", size=16, expand=True),
                            ft.IconButton(ft.Icons.EDIT, tooltip="Edit", on_click=lambda e, cc=c: self._open_form("edit", cc)),
                            ft.IconButton(
                                ft.Icons.DELETE,
                                tooltip="Delete",
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda e, cid=c["id"]: self._confirm_delete(cid),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(f"📞 {phone}", size=12, color=ft.Colors.BLUE_GREY_600),
                    ft.Text(f"✉️ {email}", size=12, color=ft.Colors.BLUE_GREY_600),
                    ft.Text(f"📍 {loc}", size=12, color=ft.Colors.BLUE_GREY_600),
                    ft.Text(f"GST: {gst}  |  NTN: {ntn}", size=12, color=ft.Colors.BLUE_GREY_600),
                ],
            ),
        )

    # ---------------- form ----------------
    def _open_form(self, mode="add", client=None):
        self.editing_client_id = None

        title = "Add Client"
        btn_text = "Save"

        if mode == "edit" and client:
            title = "Edit Client"
            btn_text = "Update"
            self.editing_client_id = client["id"]
            self._fill_form(client)
        else:
            self._clear_form()

        form_content = ft.Column(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text(title, size=18, weight="bold"),
                self.phone,
                self.email,
                ft.Row([self.gst, self.ntn], wrap=True),
                ft.Row([self.nic, self.city, self.area], wrap=True),
                self.branch_name,
                self.branch_address,
                self.billing_address,
            ],
        )

        def close(_=None):
            if sheet in self.page.overlay:
                self.page.overlay.remove(sheet)
            self.page.update()

        def submit(_):
            payload = self._payload_from_form()

            if self.editing_client_id:
                update_client(self.editing_client_id, payload)
                self._toast("✅ Client updated")
            else:
                add_client(payload)
                self._toast("✅ Client added")

            close()
            self.refresh()

        # Mobile: BottomSheet. Desktop: Dialog.
        if self.is_mobile:
            sheet = ft.BottomSheet(
                ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            form_content,
                            ft.Row(
                                [
                                    ft.OutlinedButton("Cancel", on_click=lambda e: close()),
                                    ft.ElevatedButton(btn_text, on_click=submit),
                                ],
                                alignment=ft.MainAxisAlignment.END,
                            )
                        ],
                    ),
                ),
                open=True,
            )
            self.page.overlay.append(sheet)
            self.page.update()
        else:
            sheet = ft.AlertDialog(
                modal=True,
                title=ft.Text(title),
                content=ft.Container(width=520, content=form_content),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(sheet)),
                    ft.ElevatedButton(btn_text, on_click=lambda e: (submit(e), self._close_dialog(sheet))),
                ],
            )
            self.page.overlay.append(sheet)
            sheet.open = True
            self.page.update()

    def _payload_from_form(self) -> dict:
        return {
            "person_phone": (self.phone.value or "").strip() or None,
            "person_email": (self.email.value or "").strip() or None,
            "gst": (self.gst.value or "").strip() or None,
            "ntn": (self.ntn.value or "").strip() or None,
            "nic": (self.nic.value or "").strip() or None,
            "city": (self.city.value or "").strip() or None,
            "area": (self.area.value or "").strip() or None,
            "branch_name": (self.branch_name.value or "").strip() or None,
            "branch_address": (self.branch_address.value or "").strip() or None,
            "billing_address": (self.billing_address.value or "").strip() or None,
        }

    def _fill_form(self, c: dict):
        self.phone.value = c.get("person_phone") or ""
        self.email.value = c.get("person_email") or ""
        self.gst.value = c.get("gst") or ""
        self.ntn.value = c.get("ntn") or ""
        self.nic.value = c.get("nic") or ""
        self.city.value = c.get("city") or ""
        self.area.value = c.get("area") or ""
        self.branch_name.value = c.get("branch_name") or ""
        self.branch_address.value = c.get("branch_address") or ""
        self.billing_address.value = c.get("billing_address") or ""

    def _clear_form(self):
        for f in [
            self.phone, self.email, self.gst, self.ntn,
            self.nic, self.city, self.area,
            self.branch_name, self.branch_address, self.billing_address
        ]:
            f.value = ""

    # ---------------- delete ----------------
    def _confirm_delete(self, client_id: str):
        def yes(_):
            delete_client(client_id)
            self._toast("🗑️ Client deleted")
            dlg.open = False
            self.page.update()
            self.refresh()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete client?"),
            content=ft.Text("This will remove the client permanently."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton("Delete", on_click=yes),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # ---------------- helpers ----------------
    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def _toast(self, msg: str):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(msg), open=True)
        self.page.update()
