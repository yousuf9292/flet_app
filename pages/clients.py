import flet as ft
from app.db_client import fetch_clients, add_client, update_client, delete_client


class ClientsPage(ft.Container):
    def __init__(self, page: ft.Page, on_back):
        super().__init__()
        self.page = page
        self.on_back = on_back
        self.expand = True
        self.padding = 16
        self.bgcolor = ft.Colors.BLUE_GREY_50

        # ----- state -----
        self.editing_client_id: str | None = None

        # ----- form fields -----
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

        # Buttons (we’ll toggle between Add / Update)
        self.save_btn = ft.ElevatedButton("Save Client", on_click=self._save_or_update_client)
        self.cancel_btn = ft.OutlinedButton("Cancel edit", on_click=self._cancel_edit, visible=False)

        # List
        self.clients_list = ft.ListView(expand=True, spacing=10, padding=0)

        self.content = ft.Column(
            expand=True,
            spacing=14,
            controls=[
                self._header(),
                self._form_card(),
                ft.Divider(),
                ft.Text("Clients", weight="bold", color=ft.Colors.BLUE_GREY_700),
                self.clients_list,
            ],
        )

        self.refresh()

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
                    ft.Text("Clients", size=20, weight="bold", expand=True),
                    ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", on_click=lambda e: self.refresh()),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

    def _form_card(self):
        return ft.Container(
            padding=14,
            border_radius=16,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_200),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        [
                            ft.Text("Add Client", weight="bold", size=16, expand=True),
                            self.cancel_btn,
                        ]
                    ),
                    ft.ResponsiveRow(
                        [
                            ft.Column([self.phone], col={"xs": 12, "sm": 6, "md": 3}),
                            ft.Column([self.email], col={"xs": 12, "sm": 6, "md": 3}),
                            ft.Column([self.gst], col={"xs": 12, "sm": 6, "md": 3}),
                            ft.Column([self.ntn], col={"xs": 12, "sm": 6, "md": 3}),
                        ],
                        spacing=10,
                        run_spacing=10,
                    ),
                    ft.ResponsiveRow(
                        [
                            ft.Column([self.nic], col={"xs": 12, "sm": 4}),
                            ft.Column([self.city], col={"xs": 12, "sm": 4}),
                            ft.Column([self.area], col={"xs": 12, "sm": 4}),
                        ],
                        spacing=10,
                        run_spacing=10,
                    ),
                    ft.ResponsiveRow(
                        [
                            ft.Column([self.branch_name], col={"xs": 12, "md": 4}),
                            ft.Column([self.branch_address], col={"xs": 12, "md": 4}),
                            ft.Column([self.billing_address], col={"xs": 12, "md": 4}),
                        ],
                        spacing=10,
                        run_spacing=10,
                    ),
                    ft.Row(
                        [self.save_btn],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
            ),
        )

    # ---------------- Data ----------------
    def refresh(self):
        self.clients_list.controls.clear()
        clients = fetch_clients() or []

        if not clients:
            self.clients_list.controls.append(ft.Text("No clients yet.", color=ft.Colors.GREY_600))
        else:
            for c in clients:
                self.clients_list.controls.append(self._client_card(c))

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

    def _clear_form(self):
        for f in [
            self.phone, self.email, self.gst, self.ntn,
            self.nic, self.city, self.area,
            self.branch_name, self.branch_address, self.billing_address
        ]:
            f.value = ""

    # ---------------- Add vs Update ----------------
    def _save_or_update_client(self, e):
        payload = self._payload_from_form()

        # EDIT MODE -> update
        if self.editing_client_id:
            update_client(self.editing_client_id, payload)
            self._toast("✅ Client updated")
            self._cancel_edit(None)  # resets edit mode + clears
            self.refresh()
            return

        # ADD MODE -> insert
        created = add_client(payload)
        if created:
            self._toast("✅ Client added")
            self._clear_form()
            self.refresh()
        else:
            self._toast("⚠️ Failed to add client")

    def _start_edit(self, client: dict):
        # set mode
        self.editing_client_id = client["id"]
        self.save_btn.text = "Update Client"
        self.cancel_btn.visible = True

        # fill fields
        self.phone.value = client.get("person_phone") or ""
        self.email.value = client.get("person_email") or ""
        self.gst.value = client.get("gst") or ""
        self.ntn.value = client.get("ntn") or ""
        self.nic.value = client.get("nic") or ""
        self.city.value = client.get("city") or ""
        self.area.value = client.get("area") or ""
        self.branch_name.value = client.get("branch_name") or ""
        self.branch_address.value = client.get("branch_address") or ""
        self.billing_address.value = client.get("billing_address") or ""

        self.page.update()

    def _cancel_edit(self, e):
        self.editing_client_id = None
        self.save_btn.text = "Save Client"
        self.cancel_btn.visible = False
        self._clear_form()
        self.page.update()

    # ---------------- Cards ----------------
    def _client_card(self, c: dict):
        title = c.get("branch_name") or c.get("person_email") or "Client"
        phone = c.get("person_phone") or "—"
        email = c.get("person_email") or "—"
        city = c.get("city") or ""
        area = c.get("area") or ""
        loc = f"{city} {area}".strip() or "—"

        return ft.Container(
            padding=12,
            border_radius=16,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_200),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        [
                            ft.Text(title, weight="bold", size=16, expand=True),
                            ft.IconButton(ft.Icons.EDIT, tooltip="Edit", on_click=lambda e, cc=c: self._start_edit(cc)),
                            ft.IconButton(
                                ft.Icons.DELETE,
                                tooltip="Delete",
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda e, cid=c["id"]: self._delete_client(cid),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(f"📞 {phone}", size=12, color=ft.Colors.BLUE_GREY_600),
                    ft.Text(f"✉️ {email}", size=12, color=ft.Colors.BLUE_GREY_600),
                    ft.Text(f"📍 {loc}", size=12, color=ft.Colors.BLUE_GREY_600),
                    ft.Text(f"GST: {c.get('gst') or '—'} | NTN: {c.get('ntn') or '—'}", size=12, color=ft.Colors.BLUE_GREY_600),
                ],
            ),
        )

    def _delete_client(self, client_id: str):
        # simple confirm
        def yes(_):
            delete_client(client_id)
            dlg.open = False
            self._toast("🗑️ Client deleted")
            self.refresh()

        dlg = ft.AlertDialog(
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

    # ---------------- small helpers ----------------
    def _close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def _toast(self, msg: str):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(msg), open=True)
        self.page.update()
