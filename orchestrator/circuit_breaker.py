"""Circuit breaker logic for detecting stuck states and triggering escalation."""

from dataclasses import dataclass
from enum import Enum
import config
from orchestrator.state import StateManager


class SystemStatus(Enum):
    RUNNING = "running"
    NEEDS_HUMAN = "needs_human"
    BUDGET_EXCEEDED = "budget_exceeded"
    COMPLETED = "completed"


@dataclass
class CircuitBreakerStatus:
    status: SystemStatus
    reason: str
    details: dict


class CircuitBreaker:
    def __init__(self, state: StateManager):
        self.state = state

    def check(self) -> CircuitBreakerStatus:
        """Check all circuit breaker conditions and return current status."""

        # Check token budget
        total_tokens = self.state.get_total_tokens_used()
        if total_tokens >= config.MAX_TOKENS_BUDGET:
            self.state.create_checkpoint("Budget exceeded - stopping")
            return CircuitBreakerStatus(
                status=SystemStatus.BUDGET_EXCEEDED,
                reason=f"Token budget exceeded: {total_tokens:,} / {config.MAX_TOKENS_BUDGET:,}",
                details={"tokens_used": total_tokens, "budget": config.MAX_TOKENS_BUDGET}
            )

        # Check blocked tasks
        blocked_count = self.state.get_blocked_task_count()
        if blocked_count >= config.MAX_BLOCKED_TASKS:
            self.state.create_checkpoint(f"{blocked_count} tasks blocked - needs human review")
            return CircuitBreakerStatus(
                status=SystemStatus.NEEDS_HUMAN,
                reason=f"Too many blocked tasks: {blocked_count}",
                details={"blocked_tasks": blocked_count, "threshold": config.MAX_BLOCKED_TASKS}
            )

        # Check if all tasks completed
        all_tasks = self.state.get_all_tasks()
        if all_tasks:
            completed = sum(1 for t in all_tasks if t.status.value == "completed")
            blocked = sum(1 for t in all_tasks if t.status.value == "blocked")
            total = len(all_tasks)

            if completed + blocked == total:
                if blocked == 0:
                    return CircuitBreakerStatus(
                        status=SystemStatus.COMPLETED,
                        reason="All tasks completed successfully!",
                        details={"completed": completed, "total": total}
                    )
                else:
                    return CircuitBreakerStatus(
                        status=SystemStatus.NEEDS_HUMAN,
                        reason=f"All tasks processed but {blocked} are blocked",
                        details={"completed": completed, "blocked": blocked, "total": total}
                    )

        return CircuitBreakerStatus(
            status=SystemStatus.RUNNING,
            reason="System operating normally",
            details={
                "tokens_used": total_tokens,
                "blocked_tasks": blocked_count
            }
        )

    def should_checkpoint(self) -> bool:
        """Check if we should create a checkpoint based on completed task count."""
        completed = self.state.get_completed_task_count()
        return completed > 0 and completed % config.CHECKPOINT_INTERVAL == 0

    def handle_task_failure(self, task_id: int) -> bool:
        """
        Handle a task that failed QA. Returns True if task should be retried,
        False if it should be blocked.
        """
        retries = self.state.increment_task_retries(task_id)
        task = self.state.get_task(task_id)

        if retries >= config.MAX_TASK_RETRIES:
            self.state.log(
                "task_blocked",
                f"Task '{task.name}' blocked after {retries} retries",
                agent_id=task.assigned_agent
            )
            return False  # Block the task

        self.state.log(
            "task_retry",
            f"Task '{task.name}' retry {retries}/{config.MAX_TASK_RETRIES}",
            agent_id=task.assigned_agent
        )
        return True  # Retry the task
