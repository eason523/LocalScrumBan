"""i18n — 中/英双语翻译表与查询函数。

用法:
    from kanban_app.i18n import t, set_lang, current_lang

    t("status.online_fmt", n=3)   # 带格式化参数
    set_lang("en")
"""

from __future__ import annotations

CURRENT_LANG = "zh"

STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "app.title": "商业级敏捷项目管理看板",

        "sidebar.header":        "📌 项目空间列表",
        "sidebar.new_placeholder": "新建项目名称...",

        "dashboard.progress_label": "项目整体完成度",
        "dashboard.stat.overdue":   "已延期任务",
        "dashboard.stat.urgent":    "紧急高优任务",
        "dashboard.stat.today":     "今日到期任务",
        "dashboard.no_project":     "(无项目)",

        "form.task_placeholder": "请输入任务描述...",
        "form.date_placeholder": "YYYY-MM-DD",
        "form.today_btn":        "今天",
        "form.submit_btn":       "指派任务",
        "form.default_date_invalid_msg": "日期格式无效,已回退到今天",

        "col.todo":  "📋 待处理",
        "col.doing": "⚡ 进行中",
        "col.done":  "✅ 已归档",

        "section.kanban": "📊 任务看板",

        "priority.high":   "高优 🔴",
        "priority.medium": "中优 🟡",
        "priority.low":    "低优 🟢",

        "date.today":         "今日到期",
        "date.overdue_fmt":   "已延期 {n} 天 ({date})",

        "status.offline":      "● 离线 · 等待发现节点",
        "status.online_fmt":   "● 在线 · {n} 个对等节点",
        "status.local_fmt":    "本节点 {id} · {ip}:{port}",

        "connect.btn":            "➕ 手动连接",
        "connect.title":          "连接到节点",
        "connect.prompt":         "输入对方机器的 IP (如 192.168.1.5)\n留空端口则用默认 57123;对方状态栏右侧可见完整地址",
        "connect.addr":           "IP 或 IP:端口",
        "connect.ok":             "连接",
        "connect.fail":           "连接失败,请检查 IP/端口与对方防火墙",
        "connect.ok_msg":         "已连接 {addr}",

        "dialog.title":                 "确认",
        "dialog.delete_project_fmt":    '确定要删除项目"{name}"吗?\n其名下的所有任务也将被清除。',
        "dialog.cancel":                "取消",
        "dialog.ok":                    "确定",

        "default.project.name": "默认项目",
        "default.task.1": "完成系统架构设计",
        "default.task.2": "前端看板模块开发",

        "lang.zh": "中文",
        "lang.en": "English",

        "log.peer_bind_failed":    "[peer] HTTP server bind failed: {err}",
        "log.peer_fixed_port":     "[peer] sync port (fixed): {port}",
        "log.peer_port_fallback":  "[peer] default port busy, using random: {port}",
        "log.peer_udp_bind_failed": "[peer] UDP announce bind failed on port {port}",
        "log.peer_zc_failed":      "[peer] zeroconf init failed: {err}",
        "log.peer_listening":      "[peer] node {id} listening on {ip}:{port}",
        "log.peer_bootstrap_miss": "[peer] no peer found within grace period -> standalone mode",
        "log.peer_bootstrap_ok":   "[peer] bootstrapped from {name}",
        "log.peer_added":          "[peer] + {name} @ {host}:{port}",
        "log.peer_removed":        "[peer] - {name}",
        "log.peer_broadcast_fail": "[peer] broadcast to {name} failed: {err}",
        "log.peer_bootstrap_fail": "[peer] bootstrap from {name} failed: {err}",
    },
    "en": {
        "app.title": "Agile Project Kanban",

        "sidebar.header":            "📌 Projects",
        "sidebar.new_placeholder":  "New project name...",

        "dashboard.progress_label": "Overall progress",
        "dashboard.stat.overdue":   "Overdue",
        "dashboard.stat.urgent":    "Urgent / high",
        "dashboard.stat.today":     "Due today",
        "dashboard.no_project":     "(no project)",

        "form.task_placeholder": "Enter task description...",
        "form.date_placeholder": "YYYY-MM-DD",
        "form.today_btn":        "Today",
        "form.submit_btn":       "Add task",
        "form.default_date_invalid_msg": "Invalid date, fell back to today",

        "col.todo":  "📋 To do",
        "col.doing": "⚡ In progress",
        "col.done":  "✅ Done",

        "section.kanban": "📊 Kanban board",

        "priority.high":   "High 🔴",
        "priority.medium": "Med 🟡",
        "priority.low":    "Low 🟢",

        "date.today":         "Due today",
        "date.overdue_fmt":   "Overdue {n} day(s) ({date})",

        "status.offline":      "● Offline, waiting for peers",
        "status.online_fmt":   "● Online, {n} peer(s)",
        "status.local_fmt":    "node {id}, {ip}:{port}",

        "connect.btn":            "➕ Connect manually",
        "connect.title":          "Connect to a node",
        "connect.prompt":         "Enter the other machine's IP (e.g. 192.168.1.5)\nPort defaults to 57123; full address shown on their status bar",
        "connect.addr":           "IP or IP:port",
        "connect.ok":             "Connect",
        "connect.fail":           "Connection failed. Check IP/port and their firewall.",
        "connect.ok_msg":         "Connected to {addr}",

        "dialog.title":                 "Confirm",
        "dialog.delete_project_fmt":    'Delete project "{name}"?\nAll its tasks will also be removed.',
        "dialog.cancel":                "Cancel",
        "dialog.ok":                    "OK",

        "default.project.name": "Default project",
        "default.task.1": "Complete system architecture design",
        "default.task.2": "Build frontend Kanban module",

        "lang.zh": "中文",
        "lang.en": "English",

        "log.peer_bind_failed":    "[peer] HTTP server bind failed: {err}",
        "log.peer_fixed_port":     "[peer] sync port (fixed): {port}",
        "log.peer_port_fallback":  "[peer] default port busy, using random: {port}",
        "log.peer_udp_bind_failed": "[peer] UDP announce bind failed on port {port}",
        "log.peer_zc_failed":      "[peer] zeroconf init failed: {err}",
        "log.peer_listening":      "[peer] node {id} listening on {ip}:{port}",
        "log.peer_bootstrap_miss": "[peer] no peer found within grace period -> standalone mode",
        "log.peer_bootstrap_ok":   "[peer] bootstrapped from {name}",
        "log.peer_added":          "[peer] + {name} @ {host}:{port}",
        "log.peer_removed":        "[peer] - {name}",
        "log.peer_broadcast_fail": "[peer] broadcast to {name} failed: {err}",
        "log.peer_bootstrap_fail": "[peer] bootstrap from {name} failed: {err}",
    },
}

LANGS = ["zh", "en"]


def set_lang(code: str) -> None:
    global CURRENT_LANG
    if code in STRINGS:
        CURRENT_LANG = code


def current_lang() -> str:
    return CURRENT_LANG


def t(key: str, **fmt) -> str:
    """按当前语言取翻译;缺失时回退中文;无 key 则回退 key 本身。"""
    val = STRINGS.get(CURRENT_LANG, STRINGS["zh"]).get(key)
    if val is None:
        val = STRINGS["zh"].get(key, key)
    if fmt:
        try:
            val = val.format(**fmt)
        except (KeyError, IndexError):
            pass
    return val


def priority_options() -> list:
    """CTkOptionMenu 可选值(随语言变化)。"""
    return [t("priority.medium"), t("priority.high"), t("priority.low")]


def priority_label_to_key() -> dict:
    """显示 label → priority key 反查表。"""
    return {
        t("priority.high"):   "high",
        t("priority.medium"): "medium",
        t("priority.low"):    "low",
    }
