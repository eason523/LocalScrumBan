"""task_form — 复合任务创建表单 (标题 / 优先级 / 日期 / 提交)。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk
import tkinter as tk

from kanban_app.config import COLORS, FONT_BASE
from kanban_app.i18n import priority_label_to_key, priority_options, t
from kanban_app.models import is_valid_date, today_str

if TYPE_CHECKING:
    from kanban_app.app import App


class TaskForm(ctk.CTkFrame):
    """复合任务创建表单。"""

    def __init__(self, master, app: "App"):
        super().__init__(
            master,
            fg_color=COLORS["bg_sidebar"],
            border_color=COLORS["border"],
            border_width=1, corner_radius=10,
        )
        self.app = app
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)
        self.grid_columnconfigure(4, weight=1)

        self.title_var = tk.StringVar()
        self.title_entry = ctk.CTkEntry(
            self, textvariable=self.title_var,
            placeholder_text=t("form.task_placeholder"),
            font=FONT_BASE,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_main"],
            height=40,
        )
        self.title_entry.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="ew")

        self.priority_menu = ctk.CTkOptionMenu(
            self, values=priority_options(),
            font=FONT_BASE,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_sidebar"],
            dropdown_text_color=COLORS["text_main"],
            text_color=COLORS["text_main"],
            dropdown_hover_color=COLORS["accent"],
            height=40,
        )
        self.priority_menu.set(t("priority.medium"))
        self.priority_menu.grid(row=0, column=1, padx=8, pady=16, sticky="ew")

        self.date_var = tk.StringVar(value=today_str())
        self.date_entry = ctk.CTkEntry(
            self, textvariable=self.date_var,
            placeholder_text=t("form.date_placeholder"),
            font=FONT_BASE,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_main"],
            height=40,
        )
        self.date_entry.grid(row=0, column=2, padx=8, pady=16, sticky="ew")

        self.today_btn = ctk.CTkButton(
            self, text=t("form.today_btn"), width=72, height=40,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=1,
            hover_color=COLORS["bg_card"],
            text_color=COLORS["text_main"],
            command=lambda: self.date_var.set(today_str()),
        )
        self.today_btn.grid(row=0, column=3, padx=8, pady=16, sticky="ew")

        self.submit_btn = ctk.CTkButton(
            self, text=t("form.submit_btn"),
            font=FONT_BASE,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=40,
            command=self._submit,
        )
        self.submit_btn.grid(row=0, column=4, padx=(8, 16), pady=16, sticky="ew")

    def _submit(self) -> None:
        title = self.title_var.get().strip()
        date_val = self.date_var.get().strip()
        if not title:
            return
        if not is_valid_date(date_val):
            # 简单处理: 直接回退到今天
            date_val = today_str()
            self.date_var.set(date_val)
        priority_key = priority_label_to_key().get(
            self.priority_menu.get(), "medium"
        )
        self.app.add_task(title, priority_key, date_val)
        self.title_var.set("")
        self.priority_menu.set(t("priority.medium"))
        self.date_var.set(today_str())
