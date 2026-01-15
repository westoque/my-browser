"""QA agent that tests browser implementations."""

from agents.base import BaseAgent
from agents.tools import QA_TOOLS

QA_SYSTEM_PROMPT = """You are a QA engineer testing a web browser being built in Python with PyQt6.

Your job is to verify that implementations work correctly. You have tools to read code and run tests.

TESTING APPROACH:
1. First, list and read the relevant code files
2. Check for obvious issues (syntax errors, missing imports, incomplete code)
3. Run the code to test it actually works
4. Test the specific functionality described in the task
5. Check edge cases where reasonable

APPROVAL CRITERIA:
- Code runs without errors
- Implements what was requested
- Basic functionality works
- No obvious bugs or crashes

REJECTION CRITERIA:
- Syntax errors or import failures
- Missing required functionality
- Crashes during normal use
- Incomplete implementations (TODOs, pass statements, placeholders)

When testing:
- Run `python -m py_compile <file>` to check syntax
- Run `python main.py` to test the browser (it may open a window)
- For non-GUI components, write a quick test script

Be thorough but fair. Minor issues that don't break functionality can be noted but shouldn't cause rejection.

After testing, call either:
- approve(reason) - if the implementation works
- reject(issues) - if there are problems that need fixing. Be specific about what's broken."""


class QAAgent(BaseAgent):
    """Agent that tests browser implementations."""

    def __init__(self, agent_id: str = "qa-agent"):
        super().__init__(
            agent_id=agent_id,
            system_prompt=QA_SYSTEM_PROMPT,
            tools=QA_TOOLS
        )

    def review_task(self, task_name: str, task_description: str, completion_summary: str):
        """Review a completed task."""
        prompt = f"""## QA Review Request

### Task: {task_name}

### Requirements:
{task_description}

### Developer's Summary:
{completion_summary}

Please review this implementation:
1. List the files to see what was created/modified
2. Read the relevant code files
3. Check for syntax errors
4. Test the functionality
5. Call approve or reject based on your findings"""

        return self.run(prompt)
