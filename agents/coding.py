"""Coding agent that implements browser components."""

from agents.base import BaseAgent
from agents.tools import CODING_TOOLS

CODING_SYSTEM_PROMPT = """You are an expert Python developer building a web browser. You write clean, working code.

Your task is to implement specific browser components. You have access to tools to read, write, and test files.

IMPORTANT GUIDELINES:
1. Read existing code first before making changes
2. Follow the existing code style and patterns
3. Write complete, working implementations - no placeholders or TODOs
4. Test your code by running it before marking complete
5. Use PyQt6 for all GUI components
6. Handle errors gracefully - don't let the browser crash
7. Keep code simple and readable

FILE STRUCTURE:
All your code goes in the browser/ directory:
- browser/main.py - Entry point
- browser/window.py - Main window
- browser/components/ - UI components
- browser/networking/ - HTTP client
- browser/parser/ - HTML/CSS parsing
- browser/core/ - Core logic (navigation, page loading)

When you've completed the task:
1. Make sure the code runs without syntax errors
2. Test basic functionality
3. Call the task_complete tool with a summary

If you encounter issues, debug and fix them - don't give up."""


class CodingAgent(BaseAgent):
    """Agent that writes browser code."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id=agent_id,
            system_prompt=CODING_SYSTEM_PROMPT,
            tools=CODING_TOOLS
        )

    def work_on_task(self, task_name: str, task_description: str):
        """Start working on a task."""
        prompt = f"""## Task: {task_name}

{task_description}

Start by listing the current files to understand the project state, then implement the required functionality.
When done, test your implementation and call task_complete."""

        return self.run(prompt)

    def fix_issues(self, issues: str):
        """Fix issues reported by QA."""
        prompt = f"""## QA Feedback - Issues Found

The QA agent found the following issues with your implementation:

{issues}

Please fix these issues:
1. Read the relevant code
2. Understand the problem
3. Make the necessary fixes
4. Test that the fix works
5. Call task_complete when done"""

        return self.run(prompt)
