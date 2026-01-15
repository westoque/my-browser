"""Base agent class with Claude API integration."""

import anthropic
from typing import Generator
from dataclasses import dataclass
import config
from agents.tools import execute_tool


@dataclass
class AgentResult:
    """Result from an agent run."""
    success: bool
    message: str
    tokens_used: int
    tool_name: str = None  # The final tool that was called (task_complete, approve, reject)


class BaseAgent:
    """Base class for all agents with Claude API integration."""

    def __init__(self, agent_id: str, system_prompt: str, tools: list[dict]):
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.tools = tools
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.conversation_history: list[dict] = []
        self.total_tokens = 0

    def reset_conversation(self):
        """Clear conversation history for a new task."""
        self.conversation_history = []

    def run(self, task_prompt: str, max_turns: int = None) -> AgentResult:
        """
        Run the agent with a task prompt. Continues until a terminal tool is called
        or max_turns is reached.
        """
        if max_turns is None:
            max_turns = config.MAX_AGENT_TURNS

        # Add the task to conversation
        self.conversation_history.append({
            "role": "user",
            "content": task_prompt
        })

        terminal_tools = {"task_complete", "approve", "reject"}

        for turn in range(max_turns):
            # Call Claude
            response = self.client.messages.create(
                model=config.MODEL,
                max_tokens=8096,
                system=self.system_prompt,
                tools=self.tools,
                messages=self.conversation_history
            )

            # Track tokens
            tokens_this_turn = response.usage.input_tokens + response.usage.output_tokens
            self.total_tokens += tokens_this_turn

            # Process response
            assistant_message = {"role": "assistant", "content": response.content}
            self.conversation_history.append(assistant_message)

            # Check if we need to handle tool calls
            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        print(f"  [{self.agent_id}] Tool: {tool_name}")

                        # Execute the tool
                        result = execute_tool(tool_name, tool_input)

                        # Check if this is a terminal tool
                        if tool_name in terminal_tools:
                            # Add tool result to history for completeness
                            self.conversation_history.append({
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": result
                                }]
                            })

                            return AgentResult(
                                success=tool_name in {"task_complete", "approve"},
                                message=result,
                                tokens_used=self.total_tokens,
                                tool_name=tool_name
                            )

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })

                # Add tool results to conversation
                if tool_results:
                    self.conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })

            elif response.stop_reason == "end_turn":
                # Model finished without calling a terminal tool
                # Extract text response
                text_content = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        text_content += block.text

                # If the model is done talking but didn't call a terminal tool,
                # prompt it to do so
                self.conversation_history.append({
                    "role": "user",
                    "content": "Please call the appropriate tool to indicate you're done (task_complete if you're a coding agent, or approve/reject if you're QA)."
                })

        # Max turns reached
        return AgentResult(
            success=False,
            message=f"Max turns ({max_turns}) reached without completion",
            tokens_used=self.total_tokens,
            tool_name=None
        )

    def continue_with_feedback(self, feedback: str) -> AgentResult:
        """Continue the conversation with feedback (e.g., from QA)."""
        return self.run(feedback)
