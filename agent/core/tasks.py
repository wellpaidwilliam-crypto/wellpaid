"""WellPaiD Trader - Task Manager

Task management system with persistence, priorities, and status tracking.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from enum import Enum

try:
    from agent.core.storage import sqlite_db
except ImportError:
    from .storage import sqlite_db


class TaskStatus(Enum):
    """Task status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Task:
    """Represents a single task."""
    id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    due_date: Optional[str]
    tags: list[str]


class TaskManager:
    """Task management system with persistence.
    
    Supports creating, listing, completing, and deleting tasks.
    Tasks are persisted to a JSON file.
    """
    
    def __init__(self, storage_path: str = "agent/data/tasks.db") -> None:
        """Initialize task manager.

        State is persisted in SQLite (write-through on every mutation).

        Args:
            storage_path: Path to SQLite database file
        """
        self.storage_path = Path(storage_path)
        self.tasks: dict[str, Task] = {}
        self._init_db()

    def _connect(self):
        """Open a short-lived, auto-closing connection to the store."""
        return sqlite_db(self.storage_path)

    def _init_db(self) -> None:
        """Create schema and load persisted tasks into memory."""
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tasks"
                "(id TEXT PRIMARY KEY, title TEXT, description TEXT, "
                "status TEXT, priority TEXT, created_at TEXT, "
                "updated_at TEXT, completed_at TEXT, due_date TEXT, tags TEXT)"
            )
            for r in conn.execute("SELECT * FROM tasks"):
                import json as _json

                self.tasks[r["id"]] = Task(
                    id=r["id"],
                    title=r["title"],
                    description=r["description"],
                    status=TaskStatus(r["status"]),
                    priority=TaskPriority(r["priority"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    completed_at=r["completed_at"],
                    due_date=r["due_date"],
                    tags=_json.loads(r["tags"] or "[]"),
                )

    def _persist_task(self, task: Task) -> None:
        import json as _json

        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    task.id,
                    task.title,
                    task.description,
                    task.status.value,
                    task.priority.value,
                    task.created_at,
                    task.updated_at,
                    task.completed_at,
                    task.due_date,
                    _json.dumps(task.tags),
                ),
            )

    def _delete_task_row(self, task_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    def _load(self) -> None:
        """Legacy entry point: state is loaded by _init_db at construction."""
        return None

    def _save(self) -> None:
        """Legacy entry point: persistence is write-through per mutation."""
        return None
    
    def create(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> Task:
        """Create a new task.
        
        Args:
            title: Task title
            description: Task description
            priority: Task priority
            due_date: Optional due date (ISO format)
            tags: Optional list of tags
            
        Returns:
            Created Task object
        """
        now = datetime.now().isoformat()
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now,
            updated_at=now,
            completed_at=None,
            due_date=due_date,
            tags=tags or [],
        )
        self.tasks[task.id] = task
        self._persist_task(task)
        return task
    
    def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task object or None if not found
        """
        return self.tasks.get(task_id)
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        limit: int = 50,
    ) -> list[Task]:
        """List tasks with optional filters.
        
        Args:
            status: Filter by status
            priority: Filter by priority
            limit: Maximum results
            
        Returns:
            List of Task objects
        """
        results = list(self.tasks.values())
        
        if status:
            results = [t for t in results if t.status == status]
        
        if priority:
            results = [t for t in results if t.priority == priority]
        
        # Sort by priority (critical first), then by creation time
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3,
        }
        results.sort(key=lambda t: (priority_order[t.priority], t.created_at), reverse=False)
        
        return results[:limit]
    
    def complete(self, task_id: str) -> bool:
        """Mark a task as completed.
        
        Args:
            task_id: Task ID to complete
            
        Returns:
            True if completed, False if not found
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now().isoformat()
        task.updated_at = datetime.now().isoformat()
        self._persist_task(task)
        return True
    
    def update_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update task status.
        
        Args:
            task_id: Task ID
            status: New status
            
        Returns:
            True if updated, False if not found
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.status = status
        task.updated_at = datetime.now().isoformat()
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now().isoformat()
        self._persist_task(task)
        return True
    
    def delete(self, task_id: str) -> bool:
        """Delete a task.
        
        Args:
            task_id: Task ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._delete_task_row(task_id)
            return True
        return False
    
    def count(self, status: Optional[TaskStatus] = None) -> int:
        """Count tasks.
        
        Args:
            status: Optional status to count
            
        Returns:
            Number of tasks
        """
        if status:
            return len([t for t in self.tasks.values() if t.status == status])
        return len(self.tasks)
    
    def clear(self) -> int:
        """Clear all tasks.
        
        Returns:
            Number of tasks cleared
        """
        count = len(self.tasks)
        self.tasks = {}
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks")
        return count
