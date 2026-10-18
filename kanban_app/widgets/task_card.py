"""task_card — 单张可拖拽的任务卡片。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from kanban_app.config import COLORS, FONT_BASE, FONT_TINY, PRIORITY_COLORS
from kanban_app.i18n import t
from kanban_app.models import Task, calculate_days_diff, today_str

if TYPE_CHECKING:  # 避免循环导入
    from kanban_app.app import App


class TaskCard(ctk.CTkFrame):
    """单张可拖拽的任务卡片。"""

    def __init__(self, master, app: "App", task: Task):
        # 决定边框色 (延期 = 红色, 今日 = 蓝色)
        border_color = COLORS["border"]
        if task.status != "done":
            if task.due_date < today_str():
                border_color = COLORS["danger"]
            elif task.due_date == today_str():
                border_color = COLORS["info"]

        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            border_color=border_color,
            border_width=2 if border_color != COLORS["border"] else 1,
            corner_radius=8,
        )
        self.app = app
        self.task = task

        self._build_header()
        self._build_footer()

        # 把所有子控件也绑定到拖拽事件,这样点 label/button 也能拖
        for w in (self.header_frame.winfo_children()
                  + self.footer_frame.winfo_children()):
            w.bind("<Button-1>", self._on_press)
        self.bind("<Button-1>", self._on_press)
        self.title_label.bind("<Double-Button-1>", self._on_title_double_click)

    # ------------------------------------------------------------------ UI
    def _build_header(self) -> None:
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=12, pady=(12, 6))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=self.task.title,
            font=FONT_BASE,
            text_color=COLORS["text_main"],
            anchor="w",
            justify="left",
            wraplength=220,
        )
        self.title_label.pack(side="left", fill="x", expand=True, padx=(0, 8))

        p_text, p_border = PRIORITY_COLORS[self.task.priority]
        self.priority_badge = ctk.CTkFrame(
            self.header_frame,
            fg_color="transparent",
            border_color=p_border,
            border_width=1,
            corner_radius=12,
        )
        ctk.CTkLabel(
            self.priority_badge,
            text=t("priority." + self.task.priority),
            font=FONT_TINY, text_color=p_text,
            padx=8, pady=2,
        ).pack()
        self.priority_badge.pack(side="right")

    def _build_footer(self) -> None:
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill="x", padx=12, pady=(4, 12))

        date_text, date_color, border_c, is_warn = self._format_date()
        self.date_label = ctk.CTkFrame(
            self.footer_frame,
            fg_color="transparent",
            border_color=border_c if is_warn else COLORS["bg_card"],
            border_width=1,
            corner_radius=4,
        )
        ctk.CTkLabel(
            self.date_label, text=f"📅 {date_text}",
            font=FONT_TINY, text_color=date_color,
            padx=6, pady=2,
        ).pack()
        self.date_label.pack(side="left")

        self.delete_btn = ctk.CTkButton(
            self.footer_frame,
            text="🗑️",
            width=28, height=24,
            fg_color="transparent",
            hover_color=COLORS["bg_sidebar"],
            text_color=COLORS["text_muted"],
            command=self._on_delete_click,
        )
        self.delete_btn.pack(side="right")

    def _format_date(self) -> tuple[str, str, str, bool]:
        """返回 (显示文本, 文本色, 边框色, 是否警示)。"""
        if self.task.status == "done":
            return self.task.due_date, COLORS["text_muted"], "transparent", False
        if self.task.due_date < today_str():
            diff = calculate_days_diff(self.task.due_date, today_str())
            return (t("date.overdue_fmt", n=diff, date=self.task.due_date),
                    COLORS["danger"], COLORS["danger"], True)
        if self.task.due_date == today_str():
            return t("date.today"), COLORS["info"], COLORS["info"], False
        return self.task.due_date, COLORS["text_muted"], "transparent", False

    # --------------------------------------------------------------- 交互
    def _on_delete_click(self) -> None:
        self.app.delete_task(self.task.id)

    def _on_title_double_click(self, _event=None) -> None:
        """原地把标题 label 替换为 CTkEntry。"""
        entry = ctk.CTkEntry(
            self.header_frame,
            font=FONT_BASE,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["accent"],
            text_color=COLORS["text_main"],
            width=180,
        )
        entry.insert(0, self.task.title)
        entry.focus_set()
        entry.select_all()

        committed = [False]

        def commit(_e=None):
            if committed[0]:
                return
            committed[0] = True
            new_title = entry.get().strip()
            if new_title and new_title != self.task.title:
                self.app.update_task_title(self.task.id, new_title)
            else:
                self.app.refresh()
            entry.destroy()

        def cancel(_e=None):
            if committed[0]:
                return
            committed[0] = True
            self.app.refresh()

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", cancel)

        self.title_label.pack_forget()
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    # --------------------------------------------------------------- 拖拽
    def _on_press(self, event) -> None:
        """标记这张卡为拖拽源(实际跟手逻辑在 App 中处理)。"""
        self.app._begin_drag(self, event)
