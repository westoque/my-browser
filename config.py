"""Configuration for the multi-agent browser development system."""

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent
BROWSER_DIR = PROJECT_ROOT / "browser"
DATA_DIR = PROJECT_ROOT / "data"
STATE_DB_PATH = DATA_DIR / "state.db"

# Ensure directories exist
BROWSER_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# API Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-20250514"

# Agent Configuration
NUM_CODING_AGENTS = 3
MAX_AGENT_TURNS = 50  # Max back-and-forth per task

# Circuit Breaker Settings
MAX_TASK_RETRIES = 3
MAX_BLOCKED_TASKS = 3
MAX_TOKENS_BUDGET = 2_000_000  # ~$6 at Sonnet pricing
CHECKPOINT_INTERVAL = 10  # Create checkpoint every N completed tasks

# Task timeout (seconds)
TASK_TIMEOUT = 600  # 10 minutes per task
