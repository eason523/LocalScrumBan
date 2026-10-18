"""config — 主题色板 / 字体 / 常量 / 看板列定义。"""

from __future__ import annotations

import sys

# 与 TODO.html CSS 变量严格一一对应的色板
COLORS = {
    "bg_dark":      "#0f172a",
    "bg_sidebar":   "#1e293b",
    "bg_card":      "#334155",
    "bg_input":     "#0f172a",
    "border":       "#475569",
    "text_main":    "#f8fafc",
    "text_muted":   "#94a3b8",
    "accent":       "#3b82f6",
    "accent_hover": "#2563eb",
    "danger":       "#ef4444",
    "info":         "#38bdf8",
    "warning":      "#f59e0b",
}

# 优先级: 文本色 / 边框色 (label 文案用 i18n.t() 实时拿)
PRIORITY_COLORS = {
    "high":   ("#fca5a5", "#ef4444"),
    "medium": ("#fcd34d", "#f59e0b"),
    "low":    ("#6ee7b7", "#10b981"),
}
PRIORITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}

# 看板列: (status key, i18n key);标题用 t() 拉取
KANBAN_COLUMNS = [
    ("todo",  "col.todo"),
    ("doing", "col.doing"),
    ("done",  "col.done"),
]

# 字体:Windows 用微软雅黑;其它系统退回到 sans-serif
FONT_FAMILY = "Microsoft YaHei UI" if sys.platform.startswith("win") else "Helvetica"
FONT_BASE      = (FONT_FAMILY, 13)
FONT_TITLE     = (FONT_FAMILY, 18, "bold")
FONT_SECTION   = (FONT_FAMILY, 14, "bold")
FONT_SMALL     = (FONT_FAMILY, 11)
FONT_TINY      = (FONT_FAMILY, 10)

APP_DEFAULT_SIZE = "1280x800"
APP_MIN_SIZE     = "1024x640"
