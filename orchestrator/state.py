"""SQLite-based state management for persistent orchestrator state."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IN_QA = "in_qa"
    BLOCKED = "blocked"
    COMPLETED = "completed"

class AgentStatus(Enum):
    IDLE = "idle"
    WORKING = "working"
    WAITING_QA = "waiting_qa"

@dataclass
class Task:
    id: int
    name: str
    component: str
    description: str
    status: TaskStatus
    assigned_agent: Optional[str]
    retries: int
    dependencies: list[int]
    created_at: str
    completed_at: Optional[str]

    def to_dict(self):
        d = asdict(self)
        d['status'] = self.status.value
        return d

@dataclass
class Agent:
    id: str
    agent_type: str  # "coding" or "qa"
    status: AgentStatus
    current_task_id: Optional[int]
    total_tokens_used: int
    conversation_history: list[dict]

class StateManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                component TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                assigned_agent TEXT,
                retries INTEGER DEFAULT 0,
                dependencies TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                agent_type TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                current_task_id INTEGER,
                total_tokens_used INTEGER DEFAULT 0,
                conversation_history TEXT DEFAULT '[]'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                completed_tasks INTEGER,
                total_tokens INTEGER,
                state_summary TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent_id TEXT,
                action TEXT NOT NULL,
                details TEXT
            )
        """)

        self.conn.commit()

    # Task operations
    def create_task(self, name: str, component: str, description: str,
                    dependencies: list[int] = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (name, component, description, dependencies, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, component, description,
              json.dumps(dependencies or []),
              datetime.now().isoformat()))
        self.conn.commit()
        return cursor.lastrowid

    def get_task(self, task_id: int) -> Optional[Task]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return Task(
            id=row['id'],
            name=row['name'],
            component=row['component'],
            description=row['description'],
            status=TaskStatus(row['status']),
            assigned_agent=row['assigned_agent'],
            retries=row['retries'],
            dependencies=json.loads(row['dependencies']),
            created_at=row['created_at'],
            completed_at=row['completed_at']
        )

    def get_next_pending_task(self) -> Optional[Task]:
        """Get next task that is pending and has all dependencies completed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks
            WHERE status = 'pending'
            ORDER BY id ASC
        """)

        for row in cursor.fetchall():
            dependencies = json.loads(row['dependencies'])
            if self._dependencies_met(dependencies):
                return Task(
                    id=row['id'],
                    name=row['name'],
                    component=row['component'],
                    description=row['description'],
                    status=TaskStatus(row['status']),
                    assigned_agent=row['assigned_agent'],
                    retries=row['retries'],
                    dependencies=dependencies,
                    created_at=row['created_at'],
                    completed_at=row['completed_at']
                )
        return None

    def _dependencies_met(self, dep_ids: list[int]) -> bool:
        if not dep_ids:
            return True
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(dep_ids))
        cursor.execute(f"""
            SELECT COUNT(*) FROM tasks
            WHERE id IN ({placeholders}) AND status = 'completed'
        """, dep_ids)
        return cursor.fetchone()[0] == len(dep_ids)

    def update_task_status(self, task_id: int, status: TaskStatus,
                           assigned_agent: str = None):
        cursor = self.conn.cursor()
        if status == TaskStatus.COMPLETED:
            cursor.execute("""
                UPDATE tasks SET status = ?, assigned_agent = ?, completed_at = ?
                WHERE id = ?
            """, (status.value, assigned_agent, datetime.now().isoformat(), task_id))
        else:
            cursor.execute("""
                UPDATE tasks SET status = ?, assigned_agent = ?
                WHERE id = ?
            """, (status.value, assigned_agent, task_id))
        self.conn.commit()

    def increment_task_retries(self, task_id: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE tasks SET retries = retries + 1 WHERE id = ?
        """, (task_id,))
        self.conn.commit()
        cursor.execute("SELECT retries FROM tasks WHERE id = ?", (task_id,))
        return cursor.fetchone()[0]

    def get_blocked_task_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'blocked'")
        return cursor.fetchone()[0]

    def get_completed_task_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        return cursor.fetchone()[0]

    def get_all_tasks(self) -> list[Task]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks ORDER BY id")
        tasks = []
        for row in cursor.fetchall():
            tasks.append(Task(
                id=row['id'],
                name=row['name'],
                component=row['component'],
                description=row['description'],
                status=TaskStatus(row['status']),
                assigned_agent=row['assigned_agent'],
                retries=row['retries'],
                dependencies=json.loads(row['dependencies']),
                created_at=row['created_at'],
                completed_at=row['completed_at']
            ))
        return tasks

    # Agent operations
    def register_agent(self, agent_id: str, agent_type: str):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO agents (id, agent_type, status, total_tokens_used, conversation_history)
            VALUES (?, ?, 'idle', 0, '[]')
        """, (agent_id, agent_type))
        self.conn.commit()

    def get_idle_coding_agent(self) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id FROM agents
            WHERE agent_type = 'coding' AND status = 'idle'
            LIMIT 1
        """)
        row = cursor.fetchone()
        return row['id'] if row else None

    def update_agent_status(self, agent_id: str, status: AgentStatus,
                            current_task_id: int = None):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE agents SET status = ?, current_task_id = ?
            WHERE id = ?
        """, (status.value, current_task_id, agent_id))
        self.conn.commit()

    def add_agent_tokens(self, agent_id: str, tokens: int):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE agents SET total_tokens_used = total_tokens_used + ?
            WHERE id = ?
        """, (tokens, agent_id))
        self.conn.commit()

    def get_total_tokens_used(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT SUM(total_tokens_used) FROM agents")
        result = cursor.fetchone()[0]
        return result or 0

    def save_agent_conversation(self, agent_id: str, history: list[dict]):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE agents SET conversation_history = ?
            WHERE id = ?
        """, (json.dumps(history), agent_id))
        self.conn.commit()

    def get_agent_conversation(self, agent_id: str) -> list[dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT conversation_history FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        return json.loads(row['conversation_history']) if row else []

    # Checkpoint operations
    def create_checkpoint(self, state_summary: str = ""):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO checkpoints (timestamp, completed_tasks, total_tokens, state_summary)
            VALUES (?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            self.get_completed_task_count(),
            self.get_total_tokens_used(),
            state_summary
        ))
        self.conn.commit()

    # Logging
    def log(self, action: str, details: str = "", agent_id: str = None):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO logs (timestamp, agent_id, action, details)
            VALUES (?, ?, ?, ?)
        """, (datetime.now().isoformat(), agent_id, action, details))
        self.conn.commit()

    def close(self):
        self.conn.close()
