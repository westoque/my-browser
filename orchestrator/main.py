"""Main orchestrator that coordinates agents to build the browser."""

import time
from pathlib import Path

import config
from orchestrator.state import StateManager, TaskStatus, AgentStatus
from orchestrator.task_queue import initialize_tasks
from orchestrator.circuit_breaker import CircuitBreaker, SystemStatus
from agents.coding import CodingAgent
from agents.qa import QAAgent


class Orchestrator:
    """Main orchestrator that coordinates browser development."""

    def __init__(self, resume: bool = False):
        self.state = StateManager(config.STATE_DB_PATH)
        self.circuit_breaker = CircuitBreaker(self.state)
        self.coding_agents: dict[str, CodingAgent] = {}
        self.qa_agent: QAAgent = None
        self.resume = resume

        self._setup_agents()
        if not resume:
            initialize_tasks(self.state)

    def _setup_agents(self):
        """Initialize all agents."""
        # Create coding agents
        for i in range(config.NUM_CODING_AGENTS):
            agent_id = f"coding-{i+1}"
            self.coding_agents[agent_id] = CodingAgent(agent_id)
            self.state.register_agent(agent_id, "coding")

        # Create QA agent
        self.qa_agent = QAAgent("qa-agent")
        self.state.register_agent("qa-agent", "qa")

        print(f"Initialized {len(self.coding_agents)} coding agents and 1 QA agent")

    def run(self, dry_run: bool = False):
        """Main orchestration loop."""
        print("\n" + "="*60)
        print("BROWSER DEVELOPMENT ORCHESTRATOR")
        print("="*60)

        if dry_run:
            self._show_plan()
            return

        self.state.log("orchestrator_started", f"Resume={self.resume}")

        while True:
            # Check circuit breakers
            status = self.circuit_breaker.check()
            if status.status != SystemStatus.RUNNING:
                self._handle_stop(status)
                break

            # Get next task
            task = self.state.get_next_pending_task()
            if task is None:
                # No pending tasks - check if we're done or stuck
                all_tasks = self.state.get_all_tasks()
                in_progress = [t for t in all_tasks if t.status in
                              (TaskStatus.IN_PROGRESS, TaskStatus.IN_QA)]
                if in_progress:
                    print("Waiting for in-progress tasks...")
                    time.sleep(5)
                    continue
                else:
                    print("\nNo more tasks to process!")
                    break

            # Process the task
            self._process_task(task)

            # Checkpoint if needed
            if self.circuit_breaker.should_checkpoint():
                self.state.create_checkpoint(f"Checkpoint at task {task.id}")
                print(f"[Checkpoint created]")

        self._print_summary()

    def _process_task(self, task):
        """Process a single task through coding and QA."""
        print(f"\n{'='*60}")
        print(f"TASK {task.id}: {task.name}")
        print(f"Component: {task.component}")
        print(f"{'='*60}")

        # Find an available coding agent
        agent_id = self.state.get_idle_coding_agent()
        if not agent_id:
            # All agents busy - this shouldn't happen in sequential mode
            agent_id = list(self.coding_agents.keys())[0]

        agent = self.coding_agents[agent_id]
        agent.reset_conversation()

        # Update state
        self.state.update_task_status(task.id, TaskStatus.IN_PROGRESS, agent_id)
        self.state.update_agent_status(agent_id, AgentStatus.WORKING, task.id)
        self.state.log("task_started", f"Task '{task.name}' assigned to {agent_id}", agent_id)

        print(f"\n[{agent_id}] Working on task...")

        # Coding agent works on the task
        result = agent.work_on_task(task.name, task.description)
        self.state.add_agent_tokens(agent_id, result.tokens_used)

        if not result.success:
            print(f"[{agent_id}] Failed to complete task: {result.message}")
            self._handle_task_failure(task, result.message)
            return

        print(f"[{agent_id}] Completed: {result.message}")

        # Send to QA
        self.state.update_task_status(task.id, TaskStatus.IN_QA, agent_id)
        self.state.update_agent_status(agent_id, AgentStatus.WAITING_QA, task.id)
        self.qa_agent.reset_conversation()

        print(f"\n[qa-agent] Reviewing task...")

        qa_result = self.qa_agent.review_task(task.name, task.description, result.message)
        self.state.add_agent_tokens("qa-agent", qa_result.tokens_used)

        if qa_result.tool_name == "approve":
            print(f"[qa-agent] APPROVED: {qa_result.message}")
            self.state.update_task_status(task.id, TaskStatus.COMPLETED, agent_id)
            self.state.update_agent_status(agent_id, AgentStatus.IDLE)
            self.state.log("task_completed", f"Task '{task.name}' approved", agent_id)

        elif qa_result.tool_name == "reject":
            print(f"[qa-agent] REJECTED: {qa_result.message}")
            self._handle_qa_rejection(task, agent, qa_result.message)

        else:
            # QA didn't call approve or reject properly
            print(f"[qa-agent] Unclear result, treating as rejection")
            self._handle_qa_rejection(task, agent, "QA review incomplete")

    def _handle_qa_rejection(self, task, agent, issues: str):
        """Handle a QA rejection - retry or block the task."""
        can_retry = self.circuit_breaker.handle_task_failure(task.id)

        if can_retry:
            print(f"\n[{agent.agent_id}] Fixing issues (retry {task.retries + 1})...")

            # Have the coding agent fix the issues
            fix_result = agent.fix_issues(issues)
            self.state.add_agent_tokens(agent.agent_id, fix_result.tokens_used)

            if fix_result.success:
                # Re-run QA
                self.qa_agent.reset_conversation()
                qa_result = self.qa_agent.review_task(
                    task.name, task.description, fix_result.message
                )
                self.state.add_agent_tokens("qa-agent", qa_result.tokens_used)

                if qa_result.tool_name == "approve":
                    print(f"[qa-agent] APPROVED after fix: {qa_result.message}")
                    self.state.update_task_status(task.id, TaskStatus.COMPLETED, agent.agent_id)
                    self.state.update_agent_status(agent.agent_id, AgentStatus.IDLE)
                    self.state.log("task_completed", f"Task '{task.name}' approved after retry")
                    return

            # Still failing - recursive retry handling
            updated_task = self.state.get_task(task.id)
            if updated_task.retries < config.MAX_TASK_RETRIES:
                self._handle_qa_rejection(updated_task, agent, qa_result.message if 'qa_result' in dir() else issues)
            else:
                self._block_task(task)
        else:
            self._block_task(task)

    def _block_task(self, task):
        """Mark a task as blocked."""
        self.state.update_task_status(task.id, TaskStatus.BLOCKED)
        self.state.update_agent_status(task.assigned_agent, AgentStatus.IDLE)
        self.state.log("task_blocked", f"Task '{task.name}' blocked after max retries")
        print(f"[BLOCKED] Task '{task.name}' blocked after {config.MAX_TASK_RETRIES} retries")

    def _handle_task_failure(self, task, error: str):
        """Handle a task that failed during coding (not QA)."""
        self.state.log("task_error", f"Task '{task.name}' error: {error}", task.assigned_agent)
        can_retry = self.circuit_breaker.handle_task_failure(task.id)
        if not can_retry:
            self._block_task(task)
        else:
            # Reset task to pending for retry
            self.state.update_task_status(task.id, TaskStatus.PENDING)
            self.state.update_agent_status(task.assigned_agent, AgentStatus.IDLE)

    def _handle_stop(self, status):
        """Handle orchestrator stopping."""
        print(f"\n{'='*60}")
        print(f"ORCHESTRATOR STOPPED")
        print(f"Reason: {status.reason}")
        print(f"Status: {status.status.value}")
        print(f"Details: {status.details}")
        print(f"{'='*60}")

        self.state.log("orchestrator_stopped", status.reason)

    def _show_plan(self):
        """Show the task plan without executing."""
        print("\nTASK PLAN (dry run):")
        print("-" * 40)

        tasks = self.state.get_all_tasks()
        if not tasks:
            initialize_tasks(self.state)
            tasks = self.state.get_all_tasks()

        for task in tasks:
            deps = f" (depends on: {task.dependencies})" if task.dependencies else ""
            print(f"{task.id}. [{task.component}] {task.name}{deps}")
            print(f"   Status: {task.status.value}")

        print("-" * 40)
        print(f"Total tasks: {len(tasks)}")

    def _print_summary(self):
        """Print final summary."""
        tasks = self.state.get_all_tasks()
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        blocked = sum(1 for t in tasks if t.status == TaskStatus.BLOCKED)
        pending = sum(1 for t in tasks if t.status == TaskStatus.PENDING)

        tokens = self.state.get_total_tokens_used()

        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"Tasks completed: {completed}/{len(tasks)}")
        print(f"Tasks blocked:   {blocked}")
        print(f"Tasks pending:   {pending}")
        print(f"Total tokens:    {tokens:,}")
        print(f"{'='*60}")

    def close(self):
        """Clean up resources."""
        self.state.close()
