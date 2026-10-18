"""app — 主窗口:布局编排、业务方法、拖拽、状态栏、语言切换。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from kanban_app.config import (
    APP_DEFAULT_SIZE, APP_MIN_SIZE, COLORS,
    FONT_BASE, FONT_SECTION, FONT_SMALL, KANBAN_COLUMNS,
)
from kanban_app.i18n import current_lang, priority_options, set_lang, t
from kanban_app.models import Store, Task
from kanban_app.peer import Peer, get_local_ip
from kanban_app.widgets import (
    DashboardHeader, KanbanColumn, Sidebar, TaskCard, TaskForm,
)

STORAGE_DIR = Path(os.path.expanduser("~")) / ".kanban_app"
STORAGE_FILE = STORAGE_DIR / "store.json"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(t("app.title"))
        self.geometry(APP_DEFAULT_SIZE)
        self.minsize(1024, 640)
        self.configure(fg_color=COLORS["bg_dark"])

        # 数据层
        self.store = Store(STORAGE_FILE)
        # P2P 层 (本地变更走 peer,反过来 peer 推回会回调 on_change → refresh)
        self.peer = Peer(self.store, on_change=self._schedule_refresh)

        # 拖拽状态
        self._drag_card: Optional[TaskCard] = None
        self._drag_ghost: Optional[ctk.CTkFrame] = None
        self._drag_offset = (0, 0)

        # 视图组件
        self._build_layout()
        self.refresh()

        # 启动 P2P 后台服务 (zeroconf + 内嵌 HTTP sync)
        self.peer.start()
        self.after(500, self._refresh_status_bar)

    # ------------------------------------------------------------------ UI
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0)   # sidebar
        self.grid_columnconfigure(1, weight=1)   # main
        self.grid_rowconfigure(0, weight=1)

        # 左侧栏
        self.sidebar = Sidebar(self, app=self)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # 主工作区
        self.main = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(3, weight=1)

        # 顶部 1: 统计看板
        self.dashboard = DashboardHeader(self.main, app=self)
        self.dashboard.grid(row=0, column=0, padx=24, pady=(24, 12), sticky="ew")

        # 顶部 2: 创建任务表单
        self.task_form = TaskForm(self.main, app=self)
        self.task_form.grid(row=1, column=0, padx=24, pady=(0, 18), sticky="ew")

        # 标签行
        header_row = ctk.CTkFrame(self.main, fg_color="transparent")
        header_row.grid(row=2, column=0, padx=24, pady=(0, 6), sticky="ew")
        self.section_label = ctk.CTkLabel(
            header_row, text=t("section.kanban"),
            font=FONT_SECTION,
            text_color=COLORS["text_main"],
            anchor="w",
        )
        self.section_label.pack(side="left", padx=4)

        # 三列看板
        self.board_frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.board_frame.grid(row=3, column=0, padx=24, pady=(0, 8), sticky="nsew")
        self.board_frame.grid_columnconfigure((0, 1, 2), weight=1,
                                              uniform="kanban_col")
        self.board_frame.grid_rowconfigure(0, weight=1)

        self.columns: dict[str, KanbanColumn] = {}
        for idx, (status, title_key) in enumerate(KANBAN_COLUMNS):
            col = KanbanColumn(self.board_frame, app=self,
                               title_key=title_key, status=status)
            col.grid(row=0, column=idx, padx=8, pady=4, sticky="nsew")
            self.columns[status] = col

        # 底部状态栏 (P2P 信息)
        self.status_bar = ctk.CTkFrame(
            self.main,
            fg_color=COLORS["bg_sidebar"],
            border_color=COLORS["border"], border_width=1, corner_radius=8,
        )
        self.status_bar.grid(row=4, column=0, padx=24, pady=(0, 16), sticky="ew")
        self.status_bar.grid_columnconfigure(0, weight=1)
        self.status_bar.grid_columnconfigure(1, weight=0)

        self.status_dot = ctk.CTkLabel(
            self.status_bar, text=t("status.offline"),
            font=FONT_SMALL, text_color=COLORS["text_muted"],
            anchor="w", padx=12, pady=6,
        )
        self.status_dot.grid(row=0, column=0, sticky="w")

        self.status_ip = ctk.CTkLabel(
            self.status_bar, text="",
            font=FONT_SMALL, text_color=COLORS["text_muted"],
            anchor="e", padx=12, pady=6,
        )
        self.status_ip.grid(row=0, column=1, sticky="e")

        # 手动直连按钮 (mDNS 不通时的兜底)
        self.connect_btn = ctk.CTkButton(
            self.status_bar, text=t("connect.btn"),
            width=110, height=26,
            font=FONT_SMALL,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], border_width=1,
            hover_color=COLORS["bg_card"],
            text_color=COLORS["text_main"],
            command=self._open_connect_dialog,
        )
        self.connect_btn.grid(row=0, column=2, padx=(8, 8))

    # ----------------------------------------------------------- 渲染调度
    def refresh(self) -> None:
        self.sidebar.render()
        self.dashboard.render()

        # 筛选 + 排序 (按状态分发)
        sorted_tasks = self.store.sorted_tasks_for_active()
        buckets: dict[str, list[Task]] = {s: [] for s, _ in KANBAN_COLUMNS}
        for task in sorted_tasks:
            buckets.setdefault(task.status, []).append(task)

        for status, col in self.columns.items():
            col.render(buckets.get(status, []))

    # ----------------------------------------------------------- 语言切换
    def refresh_lang(self) -> None:
        """切换语言后重建所有受影响的 widget 文案。"""
        self.title(t("app.title"))

        # Sidebar
        self.sidebar.header_label.configure(text=t("sidebar.header"))
        self.sidebar.name_entry.configure(
            placeholder_text=t("sidebar.new_placeholder"))
        self.sidebar.lang_switcher.configure(
            values=[t("lang.zh"), t("lang.en")])
        self.sidebar.lang_switcher.set(t("lang." + current_lang()))

        # Dashboard
        self.dashboard.progress_label_left.configure(
            text=t("dashboard.progress_label"))
        for _idx, (label_widget, key) in self.dashboard._stat_labels.items():
            label_widget.configure(text=t(key))

        # Section 标题
        self.section_label.configure(text=t("section.kanban"))

        # 三列看板标题
        for status, col in self.columns.items():
            for s, key in KANBAN_COLUMNS:
                if s == status:
                    col.title_label.configure(text=t(key))
                    break

        # TaskForm
        self.task_form.title_entry.configure(
            placeholder_text=t("form.task_placeholder"))
        self.task_form.date_entry.configure(
            placeholder_text=t("form.date_placeholder"))
        self.task_form.today_btn.configure(text=t("form.today_btn"))
        self.task_form.submit_btn.configure(text=t("form.submit_btn"))
        self.task_form.priority_menu.configure(values=priority_options())
        self.task_form.priority_menu.set(t("priority.medium"))

        # 卡片内容 (优先级 badge、日期格式) 在 refresh() 里重建
        self.refresh()

    # ----------------------------------------------------------- 业务方法 (全部走 P2P)
    def add_project(self, name: str) -> None:
        proj = self.peer.local_add_project(name)
        # 切到新项目 — 这是本地视图,不广播
        if proj:
            self.store.active_project_id = proj.id
            self.store.save()

    def confirm_delete_project(self, proj_id: str, proj_name: str) -> None:
        if not self._confirm(t("dialog.delete_project_fmt", name=proj_name)):
            return
        self.peer.local_delete_project(proj_id)
        # 如果删的是当前活跃项目,回退到默认
        if self.store.active_project_id == proj_id:
            for p in self.store.projects:
                if p.is_default:
                    self.store.active_project_id = p.id
                    break
            else:
                self.store.active_project_id = (
                    self.store.projects[0].id if self.store.projects else ""
                )
            self.store.save()

    def activate_project(self, proj_id: str) -> None:
        self.peer.local_activate_project(proj_id)

    def add_task(self, title: str, priority: str, due_date: str) -> None:
        if not self.store.active_project_id:
            return
        self.peer.local_add_task(self.store.active_project_id,
                                 title, priority, due_date)

    def delete_task(self, task_id: str) -> None:
        self.peer.local_delete_task(task_id)

    def update_task_title(self, task_id: str, new_title: str) -> None:
        self.peer.local_update_task_field(task_id, title=new_title)

    def update_task_status(self, task_id: str, status: str) -> None:
        # 拖拽释放时由 _on_drag_release 调用
        self.peer.local_update_task_field(task_id, status=status)

    # ----------------------------------------------------------- P2P 联动
    def _schedule_refresh(self) -> None:
        """Peer 在后台线程回调的刷新入口 —— 转入主线程。"""
        try:
            self.after(0, self.refresh)
        except Exception:
            pass

    def _refresh_status_bar(self) -> None:
        try:
            count = self.peer.peer_count()
            ip = get_local_ip()
            port = self.peer._port or 0
            if count > 0:
                self.status_dot.configure(
                    text=t("status.online_fmt", n=count),
                    text_color=COLORS["info"],
                )
            else:
                self.status_dot.configure(
                    text=t("status.offline"),
                    text_color=COLORS["warning"],
                )
            self.status_ip.configure(
                text=t("status.local_fmt",
                       id=self.peer.node_id[:8], ip=ip, port=port)
            )
        finally:
            try:
                self.after(2000, self._refresh_status_bar)
            except Exception:
                pass

    # ----------------------------------------------------------- 拖拽逻辑
    def _begin_drag(self, card: TaskCard, event) -> str | None:
        """开始拖拽 — 返回 'break' 阻止默认行为。"""
        self._drag_card = card
        self._drag_offset = (event.x_root - card.winfo_rootx(),
                             event.y_root - card.winfo_rooty())

        # 透明化原卡片,创建 ghost 跟手
        card.lift()
        card.configure(fg_color=COLORS["bg_input"])

        ghost_w = max(card.winfo_width(), 240)
        ghost_h = max(card.winfo_height(), 80)
        self._drag_ghost = ctk.CTkFrame(
            self,
            width=ghost_w, height=ghost_h,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["accent"],
            border_width=2, corner_radius=8,
        )
        ctk.CTkLabel(
            self._drag_ghost, text=card.task.title,
            font=FONT_BASE, text_color=COLORS["text_main"],
            anchor="w", wraplength=ghost_w - 30,
        ).pack(fill="both", expand=True, padx=14, pady=14)

        self._drag_ghost.place(
            x=event.x_root - self._drag_offset[0] - self.winfo_rootx(),
            y=event.y_root - self._drag_offset[1] - self.winfo_rooty(),
        )

        self.bind("<B1-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_drag_release)
        self._poll_drop_hover()
        return "break"

    def _poll_drop_hover(self) -> None:
        """轮询鼠标坐标,高亮当前悬停的看板列。"""
        if not self._drag_ghost:
            return
        x_root, y_root = self.winfo_pointerxy()
        hit = None
        for status, col in self.columns.items():
            if col.contains_point(x_root, y_root):
                hit = status
                break
        for status, col in self.columns.items():
            col.highlight(status == hit)
        self.after(50, self._poll_drop_hover)

    def _on_drag_motion(self, event) -> None:
        if self._drag_ghost:
            self._drag_ghost.place(
                x=event.x_root - self._drag_offset[0] - self.winfo_rootx(),
                y=event.y_root - self._drag_offset[1] - self.winfo_rooty(),
            )

    def _on_drag_release(self, event) -> str:
        self.unbind("<B1-Motion>")
        self.unbind("<ButtonRelease-1>")

        target_status = None
        for status, col in self.columns.items():
            col.highlight(False)
            if col.contains_point(event.x_root, event.y_root):
                target_status = status

        # 清理 ghost
        if self._drag_ghost is not None:
            self._drag_ghost.destroy()
            self._drag_ghost = None

        # 还原原卡片颜色 + 更新状态
        changed = False
        if self._drag_card is not None:
            self._drag_card.configure(fg_color=COLORS["bg_card"])
            # 只有真正跨列才刷新 — 纯点击不重建卡片,
            # 否则双击内联编辑会被销毁的 widget 打断
            if (target_status and self._drag_card.winfo_exists()
                    and target_status != self._drag_card.task.status):
                self.update_task_status(self._drag_card.task.id, target_status)
                changed = True
            self._drag_card = None

        if changed:
            self.refresh()
        return "break"

    # ----------------------------------------------------------- 手动连接
    def _open_connect_dialog(self) -> None:
        """弹窗输入 IP:PORT 直连对等节点 (绕过 mDNS)。"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(t("connect.title"))
        dialog.geometry("420x220")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text=t("connect.prompt"),
                     font=FONT_BASE, text_color=COLORS["text_muted"],
                     wraplength=380, justify="left",
                     ).pack(padx=20, pady=(18, 12), fill="x")

        entry_var = ctk.StringVar(value="")
        entry = ctk.CTkEntry(
            dialog, textvariable=entry_var,
            placeholder_text=t("connect.addr"),
            font=FONT_BASE, width=220, height=36,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_main"],
        )
        entry.pack(pady=(0, 12))
        entry.focus_set()

        msg_label = ctk.CTkLabel(dialog, text="",
                                 font=FONT_SMALL, text_color=COLORS["text_muted"],
                                 wraplength=380)
        msg_label.pack(pady=(0, 10), fill="x")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=(0, 14))

        def try_connect():
            raw = entry_var.get().strip()
            # 容错: 纯 IP 时用默认端口 57123
            if ":" not in raw:
                host, port = raw, 57123
            else:
                try:
                    host, port_s = raw.rsplit(":", 1)
                    port = int(port_s)
                    if not (0 < port < 65536):
                        raise ValueError
                except ValueError:
                    msg_label.configure(text=t("connect.fail"),
                                        text_color=COLORS["danger"])
                    return
            msg_label.configure(text="...", text_color=COLORS["text_muted"])
            dialog.update()

            ok = self.peer.add_manual_peer(host.strip(), port)
            if ok:
                msg_label.configure(
                    text=t("connect.ok_msg", addr=raw),
                    text_color=COLORS["info"])
                self.after(1200, dialog.destroy)
            else:
                msg_label.configure(text=t("connect.fail"),
                                    text_color=COLORS["danger"])

        def on_enter(_e=None):
            try_connect()

        entry.bind("<Return>", on_enter)

        ctk.CTkButton(btn_row, text=t("dialog.cancel"), width=100, height=36,
                      fg_color=COLORS["bg_card"],
                      hover_color=COLORS["border"],
                      command=dialog.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text=t("connect.ok"), width=100, height=36,
                      fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      command=try_connect).pack(side="left", padx=8)

    # ----------------------------------------------------------- 工具
    def _confirm(self, message: str) -> bool:
        """用顶层 CTkToplevel 当简易确认对话框。"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(t("dialog.title"))
        dialog.geometry("360x150")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.resizable(False, False)

        result = [False]

        ctk.CTkLabel(dialog, text=message, font=FONT_BASE,
                     text_color=COLORS["text_main"],
                     wraplength=320, justify="left"
                     ).pack(padx=20, pady=(20, 14), fill="x")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=(0, 14))

        def yes():
            result[0] = True
            dialog.destroy()

        def no():
            dialog.destroy()

        ctk.CTkButton(btn_row, text=t("dialog.cancel"), width=100, height=36,
                      fg_color=COLORS["bg_card"],
                      hover_color=COLORS["border"],
                      command=no).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text=t("dialog.ok"), width=100, height=36,
                      fg_color=COLORS["danger"],
                      hover_color="#b91c1c",
                      command=yes).pack(side="left", padx=8)

        dialog.wait_window()
        return result[0]
