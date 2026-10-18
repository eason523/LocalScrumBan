"""
kanban_app — 商业级敏捷项目管理看板 (P2P 局域网协作版)

1:1 Python + CustomTkinter 复刻 TODO.html 的桌面实现,叠加局域网 P2P 多机协作。

包结构:
    kanban_app.i18n     中/英双语翻译表
    kanban_app.config   主题色板 / 字体 / 常量
    kanban_app.models   Project / Task / Store 数据层
    kanban_app.peer     zeroconf mDNS 发现 + 内嵌 HTTP 同步 (P2P 层)
    kanban_app.widgets  可复用 UI 组件
    kanban_app.app      主窗口

依赖:  customtkinter >= 5.2.0, zeroconf >= 0.131.0
"""

__version__ = "1.4.0"
APP_NAME = "ScrumBan"
APP_AUTHOR = "ScrumBan Team"
