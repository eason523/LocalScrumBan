"""dashboard — 顶部统计看板 (项目名 + 进度条 + 三张统计卡片)。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from kanban_app.config import COLORS, FONT_BASE, FONT_FAMILY, FONT_SMALL, FONT_TITLE
from kanban_app.i18n import t

if TYPE_CHECKING:
    from kanban_app.app import App


class DashboardHeader(ctk.CTkFrame):
    """顶部统计看板 + 进度条。"""

    def __init__(self, master, app: "App"):
        super().__init__(
            master,
            fg_color=COLORS["bg_sidebar"],
            border_color=COLORS["border"],
            border_width=1, corner_radius=10,
        )
        self.app = app
        # column_idx -> (label_widget, i18n key);供 refresh_lang 走查
        self._stat_labels: dict[int, tuple[ctk.CTkLabel, str]] = {}

        self.title_label = ctk.CTkLabel(
            self, text="", font=FONT_TITLE,
            text_color=COLORS["text_main"], anchor="w",
        )
        self.title_label.pack(fill="x", padx=20, pady=(20, 14))

        # 进度条容器
        progress_container = ctk.CTkFrame(self, fg_color="transparent")
        progress_container.pack(fill="x", padx=20, pady=(0, 16))

        info_frame = ctk.CTkFrame(progress_container, fg_color="transparent")
        info_frame.pack(fill="x")
        self.progress_label_left = ctk.CTkLabel(
            info_frame, text=t("dashboard.progress_label"),
            font=FONT_BASE, text_color=COLORS["text_muted"], anchor="w",
        )
        self.progress_label_left.pack(side="left")
        self.progress_label_right = ctk.CTkLabel(
            info_frame, text="0%",
            font=FONT_BASE, text_color=COLORS["text_muted"], anchor="e",
        )
        self.progress_label_right.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            progress_container,
            height=10, corner_radius=5,
            fg_color=COLORS["bg_input"],
            progress_color=COLORS["accent"],
        )
        self.progress_bar.pack(fill="x", pady=(6, 0))
        self.progress_bar.set(0)

        # 三栏统计
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=(0, 20))
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.stat_overdue = self._make_stat_card(
            stats_frame, 0, "dashboard.stat.overdue", COLORS["danger"])
        self.stat_urgent = self._make_stat_card(
            stats_frame, 1, "dashboard.stat.urgent", COLORS["warning"])
        self.stat_today = self._make_stat_card(
            stats_frame, 2, "dashboard.stat.today", COLORS["info"])

    def _make_stat_card(self, master, col: int, label_key: str, val_color: str):
        card = ctk.CTkFrame(
            master,
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["border"],
            border_width=1, corner_radius=8,
        )
        card.grid(row=0, column=col, padx=8, sticky="ew")
        label_widget = ctk.CTkLabel(
            card, text=t(label_key),
            font=FONT_SMALL, text_color=COLORS["text_muted"],
            anchor="w",
        )
        label_widget.pack(fill="x", padx=14, pady=(14, 0))
        val = ctk.CTkLabel(
            card, text="0",
            font=(FONT_FAMILY, 24, "bold"),
            text_color=val_color, anchor="w",
        )
        val.pack(fill="x", padx=14, pady=(4, 14))
        self._stat_labels[col] = (label_widget, label_key)
        return val

    def render(self) -> None:
        proj = self.app.store.active_project()
        if proj:
            self.title_label.configure(text=proj.name)
        else:
            self.title_label.configure(text=t("dashboard.no_project"))

        stats = self.app.store.stats_for_active()
        tasks = self.app.store.tasks_for_active()
        total = len(tasks)
        percent = (stats["done"] / total) if total else 0

        self.progress_bar.set(percent)
        self.progress_label_right.configure(
            text=f"{int(percent * 100)}% ({stats['done']}/{total})"
        )
        self.stat_overdue.configure(text=str(stats["overdue"]))
        self.stat_urgent.configure(text=str(stats["urgent"]))
        self.stat_today.configure(text=str(stats["due_today"]))
