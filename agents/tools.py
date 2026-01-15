"""Tool definitions and implementations for agents."""

import os
import subprocess
from pathlib import Path
from typing import Any
import config

# Tool definitions for Claude API
CODING_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Use this to examine existing code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to browser/ directory"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Creates parent directories as needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to browser/ directory"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_files",
        "description": "List files and directories in a path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to list, relative to browser/ directory. Use '.' for browser root."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_command",
        "description": "Run a shell command. Use for running Python scripts, tests, or checking syntax.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to run. Will be executed from the browser/ directory."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "task_complete",
        "description": "Signal that you have completed the assigned task. Call this when you're done and ready for QA review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what was implemented"
                }
            },
            "required": ["summary"]
        }
    }
]

QA_TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file to review the code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file relative to browser/ directory"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_files",
        "description": "List files and directories in a path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to list, relative to browser/ directory. Use '.' for browser root."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_command",
        "description": "Run a shell command to test the implementation. Use for running the browser, tests, or checking functionality.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to run. Will be executed from the browser/ directory."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "approve",
        "description": "Approve the implementation. Call this when the code works correctly.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for approval - what tests passed"
                }
            },
            "required": ["reason"]
        }
    },
    {
        "name": "reject",
        "description": "Reject the implementation. Call this when there are bugs or issues that need fixing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issues": {
                    "type": "string",
                    "description": "Detailed description of the issues found. Be specific about what's broken and how to reproduce."
                }
            },
            "required": ["issues"]
        }
    }
]


def execute_tool(tool_name: str, tool_input: dict[str, Any], browser_dir: Path = None) -> str:
    """Execute a tool and return the result as a string."""
    if browser_dir is None:
        browser_dir = config.BROWSER_DIR

    try:
        if tool_name == "read_file":
            return _read_file(browser_dir, tool_input["path"])
        elif tool_name == "write_file":
            return _write_file(browser_dir, tool_input["path"], tool_input["content"])
        elif tool_name == "list_files":
            return _list_files(browser_dir, tool_input["path"])
        elif tool_name == "run_command":
            return _run_command(browser_dir, tool_input["command"])
        elif tool_name == "task_complete":
            return f"Task marked complete: {tool_input['summary']}"
        elif tool_name == "approve":
            return f"APPROVED: {tool_input['reason']}"
        elif tool_name == "reject":
            return f"REJECTED: {tool_input['issues']}"
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"


def _read_file(browser_dir: Path, path: str) -> str:
    """Read a file from the browser directory."""
    file_path = browser_dir / path
    if not file_path.exists():
        return f"Error: File not found: {path}"
    if not file_path.is_file():
        return f"Error: Not a file: {path}"
    # Security: ensure we're still within browser_dir
    try:
        file_path.resolve().relative_to(browser_dir.resolve())
    except ValueError:
        return "Error: Access denied - path outside browser directory"

    content = file_path.read_text()
    return content if content else "(empty file)"


def _write_file(browser_dir: Path, path: str, content: str) -> str:
    """Write content to a file in the browser directory."""
    file_path = browser_dir / path

    # Security: ensure we're still within browser_dir
    try:
        file_path.resolve().relative_to(browser_dir.resolve())
    except ValueError:
        return "Error: Access denied - path outside browser directory"

    # Create parent directories
    file_path.parent.mkdir(parents=True, exist_ok=True)

    file_path.write_text(content)
    return f"Successfully wrote {len(content)} bytes to {path}"


def _list_files(browser_dir: Path, path: str) -> str:
    """List files in a directory."""
    dir_path = browser_dir / path
    if not dir_path.exists():
        return f"Error: Directory not found: {path}"
    if not dir_path.is_dir():
        return f"Error: Not a directory: {path}"

    entries = []
    for entry in sorted(dir_path.iterdir()):
        if entry.is_dir():
            entries.append(f"[DIR]  {entry.name}/")
        else:
            size = entry.stat().st_size
            entries.append(f"[FILE] {entry.name} ({size} bytes)")

    if not entries:
        return "(empty directory)"
    return "\n".join(entries)


def _run_command(browser_dir: Path, command: str) -> str:
    """Run a shell command in the browser directory."""
    # Security: basic command sanitization
    dangerous = ["rm -rf", "sudo", "> /", "| sh", "| bash", "wget", "curl"]
    for d in dangerous:
        if d in command.lower():
            return f"Error: Command blocked for safety: {command}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(browser_dir),
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHONPATH": str(browser_dir)}
        )

        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        output += f"Exit code: {result.returncode}"

        return output if output.strip() else "(no output)"

    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error running command: {str(e)}"
