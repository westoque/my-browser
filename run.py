#!/usr/bin/env python3
"""Entry point for the multi-agent browser development system."""

import argparse
import sys

import config


def main():
    parser = argparse.ArgumentParser(
        description="Multi-agent system to build a web browser"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint instead of starting fresh"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show task plan without executing"
    )
    parser.add_argument(
        "--max-budget",
        type=int,
        default=config.MAX_TOKENS_BUDGET,
        help=f"Maximum token budget (default: {config.MAX_TOKENS_BUDGET:,})"
    )

    args = parser.parse_args()

    # Validate API key
    if not config.ANTHROPIC_API_KEY:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    # Update config with CLI args
    config.MAX_TOKENS_BUDGET = args.max_budget

    # Import here to avoid issues if API key is missing
    from orchestrator.main import Orchestrator

    print("="*60)
    print("MULTI-AGENT BROWSER DEVELOPMENT SYSTEM")
    print("="*60)
    print(f"Model: {config.MODEL}")
    print(f"Token budget: {config.MAX_TOKENS_BUDGET:,}")
    print(f"Coding agents: {config.NUM_CODING_AGENTS}")
    print(f"Max retries per task: {config.MAX_TASK_RETRIES}")
    print("="*60)

    orchestrator = Orchestrator(resume=args.resume)
    try:
        orchestrator.run(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Creating checkpoint...")
        orchestrator.state.create_checkpoint("User interrupt")
        print("Checkpoint saved. Run with --resume to continue.")
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
