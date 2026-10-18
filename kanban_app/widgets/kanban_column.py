"""kanban_column — 单列看板容器 (标题 + 计数 + 可滚动任务区 + 拖拽高亮)。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from kanban_app.config import COLORS, FONT_SECTION, FONT_TINY
from kanban_app.i18n import t
from kanban_app.models import Task
from kanban_app.widgets.task_card import TaskCard

if TYPE_CHECKING:
    from kanban_app.app import App


class KanbanColumn(ctk.CTkFrame):
    """单列看板容器。"""

    def __init__(self, master, app: "App", title_key: str, status: str):
        super().__init__(
            master,
            fg_color=COLORS["bg_sidebar"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10,
        )
        self.app = app
        self.status = status
        self._title_key = title_key

        # 头 (标题 + 计数)
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=16, pady=(16, 0))

        self.title_label = ctk.CTkLabel(
            self.header, text=t(title_key),
            font=FONT_SECTION,
            text_color=COLORS["text_main"],
            anchor="w",
        )
        self.title_label.pack(side="left")

        self.count_badge = ctk.CTkFrame(
            self.header,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10,
        )
        self._count_label = ctk.CTkLabel(
            self.count_badge, text="0",
            font=FONT_TINY, text_color=COLORS["text_muted"],
            padx=8, pady=2,
        )
        self._count_label.pack()
        self.count_badge.pack(side="right")

        # 分割线
        ctk.CTkFrame(self, height=1, fg_color=COLORS["border"]).pack(
            fill="x", padx=16, pady=(10, 8),
        )

        # 任务滚动区
        self.task_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        self.task_frame.pack(fill="both", expand=True, padx=8, pady=(0, 12))

    def render(self, tasks: list[Task]) -> None:
        """清空并重新渲染本列任务。"""
        for child in self.task_frame.winfo_children():
            child.destroy()
        for task in tasks:
            TaskCard(self.task_frame, app=self.app, task=task).pack(
                fill="x", padx=4, pady=6,
            )
        self._count_label.configure(text=str(len(tasks)))

    def highlight(self, on: bool) -> None:
        """拖拽悬停时给整列加亮蓝视觉提示。"""
        self.configure(
            border_color=COLORS["accent"] if on else COLORS["border"],
            border_width=2 if on else 1,
        )

    def contains_point(self, x_root: int, y_root: int) -> bool:
        """判断某个屏幕坐标点是否落在本列范围内 (含任务列表区)。"""
        lx = self.winfo_rootx()
        ly = self.winfo_rooty()
        lw = self.winfo_width()
        lh = self.winfo_height()
        return lx <= x_root <= lx + lw and ly <= y_root <= ly + lh
