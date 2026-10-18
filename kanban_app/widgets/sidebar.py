"""sidebar — 左侧项目空间列表面板 (含语言切换器)。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk
import tkinter as tk

from kanban_app.config import COLORS, FONT_BASE, FONT_FAMILY, FONT_SECTION, FONT_SMALL
from kanban_app.i18n import current_lang, set_lang, t

if TYPE_CHECKING:
    from kanban_app.app import App


class Sidebar(ctk.CTkFrame):
    """左侧项目空间列表面板。"""

    def __init__(self, master, app: "App"):
        super().__init__(
            master,
            width=280,
            fg_color=COLORS["bg_sidebar"],
            border_color=COLORS["border"],
            border_width=0,
        )
        self.app = app
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # -------- Header --------
        self.header_label = ctk.CTkLabel(
            self,
            text=t("sidebar.header"),
            font=FONT_SECTION,
            text_color=COLORS["info"],
            anchor="w",
        )
        self.header_label.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")

        # -------- 语言切换 --------
        self.lang_switcher = ctk.CTkSegmentedButton(
            self,
            values=[t("lang.zh"), t("lang.en")],
            font=FONT_SMALL,
            fg_color=COLORS["bg_input"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["bg_input"],
            unselected_hover_color=COLORS["bg_card"],
            text_color=COLORS["text_main"],
            command=self._on_language_changed,
        )
        self.lang_switcher.set(t("lang." + current_lang()))
        self.lang_switcher.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="ew")

        # -------- 新建项目表单 --------
        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.grid(row=2, column=0, padx=20, pady=(0, 16), sticky="ew")
        form_frame.grid_columnconfigure(0, weight=1)

        self.entry_var = tk.StringVar()
        self.name_entry = ctk.CTkEntry(
            form_frame,
            textvariable=self.entry_var,
            placeholder_text=t("sidebar.new_placeholder"),
            font=FONT_BASE,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_main"],
            height=36,
        )
        self.name_entry.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.name_entry.bind("<Return>", lambda _e: self._submit())

        add_btn = ctk.CTkButton(
            form_frame, text="+", width=36, height=36,
            font=(FONT_FAMILY, 16, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self._submit,
        )
        add_btn.grid(row=0, column=1)

        # -------- 项目列表 --------
        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        self.list_frame.grid(row=3, column=0, padx=12, pady=(0, 16),
                             sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)

    def _submit(self) -> None:
        name = self.entry_var.get().strip()
        if name:
            self.app.add_project(name)
            self.entry_var.set("")

    def _on_language_changed(self, value: str) -> None:
        # value 是当前显示的 label ("中文" 或 "English")
        new = "en" if value == t("lang.en") else "zh"
        set_lang(new)
        self.app.refresh_lang()

    def render(self) -> None:
        """重绘项目列表。"""
        for child in self.list_frame.winfo_children():
            child.destroy()

        for idx, proj in enumerate(self.app.store.projects):
            is_active = proj.id == self.app.store.active_project_id
            row = ctk.CTkFrame(
                self.list_frame,
                fg_color=COLORS["accent"] if is_active else "transparent",
                corner_radius=6,
                height=40,
            )
            row.grid(row=idx, sticky="ew", pady=3)
            row.grid_columnconfigure(0, weight=1)
            row.grid_propagate(False)

            label = ctk.CTkLabel(
                row, text=proj.name,
                font=FONT_BASE,
                text_color="white" if is_active else COLORS["text_main"],
                anchor="w",
            )
            label.grid(row=0, column=0, padx=12, pady=8, sticky="ew")

            row.bind("<Button-1>",
                     lambda _e, pid=proj.id: self.app.activate_project(pid))
            label.bind("<Button-1>",
                       lambda _e, pid=proj.id: self.app.activate_project(pid))

            if not proj.is_default:
                del_btn = ctk.CTkButton(
                    row, text="✕", width=24, height=24,
                    fg_color="transparent",
                    hover_color=COLORS["bg_sidebar"],
                    text_color=COLORS["text_muted"],
                )
                del_btn.grid(row=0, column=1, padx=(0, 8))
                del_btn.configure(command=lambda pid=proj.id, pname=proj.name:
                                  self.app.confirm_delete_project(pid, pname))
