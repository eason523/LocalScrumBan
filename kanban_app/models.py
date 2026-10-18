"""models — Project / Task 数据模型与 JSON 持久化 Store。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from kanban_app.config import PRIORITY_WEIGHT
from kanban_app.i18n import t


@dataclass
class Project:
    id: str
    name: str
    is_default: bool = False
    lamport: int = 0
    origin: str = ""   # 写入此记录的节点 UUID


@dataclass
class Task:
    id: str
    project_id: str
    title: str
    priority: str        # "high" | "medium" | "low"
    due_date: str        # ISO 格式: YYYY-MM-DD
    status: str          # "todo" | "doing" | "done"
    lamport: int = 0
    origin: str = ""


class Store:
    """基于 JSON 的内存数据仓库。"""

    def __init__(self, path: Path):
        self.path = path
        self.projects: list[Project] = []
        self.tasks: list[Task] = []
        self.active_project_id: str = ""
        self.node_id: str = ""   # 由 Peer 在构造时分配
        # 墓碑: 已删除实体 id -> 删除时的 lamport。
        # 反熵合并时据此丢弃对端拉回的已删实体,防止"复活"。
        self.deleted: dict[str, int] = {}
        self.load()

    # -------- I/O --------
    def load(self) -> None:
        if not self.path.exists():
            self._seed_defaults()
            self.save()
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("store root is not an object")
            self.projects = [self._project_from(p) for p in data.get("projects", [])]
            self.projects = [p for p in self.projects if p is not None]
            self.tasks = [self._task_from(d) for d in data.get("tasks", [])]
            self.tasks = [t for t in self.tasks if t is not None]
            self.active_project_id = str(data.get("active_project_id", "") or "")
            self.node_id = str(data.get("node_id", "") or "")
            deleted = data.get("deleted", {})
            self.deleted = {str(k): int(v) for k, v in deleted.items()
                            if isinstance(v, (int, float))} \
                if isinstance(deleted, dict) else {}
        except (json.JSONDecodeError, ValueError, TypeError, OSError):
            # 损坏文件先备份再重播种,避免用户数据被静默覆盖丢失
            try:
                backup = self.path.with_suffix(
                    self.path.suffix + ".corrupt-" +
                    datetime.now().strftime("%Y%m%d-%H%M%S"))
                self.path.replace(backup)
            except OSError:
                pass
            self._seed_defaults()
            self.save()
            return

        if not self.projects:
            self._seed_defaults()
            self.save()

    @staticmethod
    def _project_from(raw) -> Optional[Project]:
        """宽容构造: 忽略未知字段/畸形条目,不让单条脏数据搞崩启动。"""
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            return None
        return Project(
            id=raw["id"],
            name=str(raw.get("name", "")),
            is_default=bool(raw.get("is_default", False)),
            lamport=int(raw.get("lamport", 0) or 0),
            origin=str(raw.get("origin", "") or ""),
        )

    @staticmethod
    def _task_from(raw) -> Optional[Task]:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            return None
        return Task(
            id=raw["id"],
            project_id=str(raw.get("project_id", "") or ""),
            title=str(raw.get("title", "") or ""),
            priority=str(raw.get("priority", "medium")),
            due_date=str(raw.get("due_date", today_str())),
            status=str(raw.get("status", "todo")),
            lamport=int(raw.get("lamport", 0) or 0),
            origin=str(raw.get("origin", "") or ""),
        )

    def save(self) -> None:
        """原子写: 先写临时文件再 rename,进程中断不会留下半截 JSON。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "projects": [asdict(p) for p in self.projects],
            "tasks":    [asdict(t) for t in self.tasks],
            "active_project_id": self.active_project_id,
            "node_id": self.node_id,
            "deleted": self.deleted,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            tmp.replace(self.path)
        except OSError:
            # tmp 写失败时尽量清理;store.json 保持旧内容
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    # -------- 计算 --------
    def active_project(self) -> Optional[Project]:
        for p in self.projects:
            if p.id == self.active_project_id:
                return p
        return self.projects[0] if self.projects else None

    def normalize_active_project(self) -> bool:
        """活跃项目 id 悬空时回退到默认/第一个项目。返回是否发生变化。"""
        if self.active_project_id and any(
                p.id == self.active_project_id for p in self.projects):
            return False
        fallback = ""
        for p in self.projects:
            if p.is_default:
                fallback = p.id
                break
        if not fallback and self.projects:
            fallback = self.projects[0].id
        if fallback != self.active_project_id:
            self.active_project_id = fallback
            return True
        return False

    def tasks_for_active(self) -> list[Task]:
        return [t for t in self.tasks if t.project_id == self.active_project_id]

    def stats_for_active(self) -> dict:
        today = today_str()
        overdue = urgent = due_today = done = 0
        for t in self.tasks_for_active():
            if t.status == "done":
                done += 1
            else:
                if t.due_date < today:
                    overdue += 1
                if t.due_date == today:
                    due_today += 1
            if t.priority == "high":
                urgent += 1
        return {"overdue": overdue, "urgent": urgent,
                "due_today": due_today, "done": done}

    def sorted_tasks_for_active(self) -> list[Task]:
        """智能排序: 截止日期升序 → 优先级降序。"""
        def key(t: Task):
            return (t.due_date, -PRIORITY_WEIGHT[t.priority])
        return sorted(self.tasks_for_active(), key=key)

    # -------- 默认种子数据 --------
    def _seed_defaults(self) -> None:
        default_proj = Project(id="proj-default",
                               name=t("default.project.name"), is_default=True)
        self.projects = [default_proj]
        self.active_project_id = default_proj.id
        self.tasks = [
            Task(id="task-1", project_id=default_proj.id,
                 title=t("default.task.1"),
                 priority="high", due_date=offset_date(-2), status="todo"),
            Task(id="task-2", project_id=default_proj.id,
                 title=t("default.task.2"),
                 priority="medium", due_date=today_str(), status="doing"),
        ]


# ============================================================================
# 工具函数
# ============================================================================

def today_str() -> str:
    return date.today().isoformat()


def offset_date(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def calculate_days_diff(d1: str, d2: str) -> int:
    a = datetime.strptime(d1, "%Y-%m-%d").date()
    b = datetime.strptime(d2, "%Y-%m-%d").date()
    return abs((b - a).days)


def is_valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False
