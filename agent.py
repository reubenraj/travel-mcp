"""
agent.py

The agentic loop that connects Claude to the MCP tools.

Flow:
  1. Claude receives the member's message + tool definitions
  2. Claude decides which tools to call (and in what order)
  3. We execute each tool call and feed results back
  4. Claude synthesises a final recommendation response
  5. Loop ends when Claude stops calling tools (stop_reason = end_turn)
"""

import os
from typing import List
import anthropic
from dotenv import load_dotenv

from rules_engine import Recommendation
from mcp_server import get_member_profile, get_partner_rules, get_recommendations

load_dotenv()

# ── Tool registry ──────────────────────────────────────────────────────────────
# Maps tool names Claude will call to actual Python functions.
TOOL_REGISTRY = {
    "get_member_profile":   get_member_profile,
    "get_partner_rules":    get_partner_rules,
    "get_recommendations":  get_recommendations,
}

# ── Tool definitions (what Claude sees as its menu) ───────────────────────────
TOOL_DEFINITIONS = [
    {
        "name": "get_member_profile",
        "description": (
            "Fetches a member's profile and recent travel history. "
            "Always call this first — it returns the partner_id needed "
            "for subsequent tool calls."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "member_id": {
                    "type": "string",
                    "description": "The member's unique identifier (e.g. MBR001)"
                }
            },
            "required": ["member_id"]
        }
    },
    {
        "name": "get_partner_rules",
        "description": (
            "Fetches partner-specific configuration rules including "
            "recommendation caps and excluded categories. "
            "Call this after get_member_profile using the partner_id it returned."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "partner_id": {
                    "type": "string",
                    "description": "The partner's unique identifier (e.g. PARTNER_A)"
                }
            },
            "required": ["partner_id"]
        }
    },
    {
        "name": "get_recommendations",
        "description": (
            "Fetches travel recommendations with all partner rules enforced. "
            "Returns only rule-compliant recommendations — categories are already "
            "filtered and results are already capped. "
            "Use these recommendations to craft your response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "member_id": {
                    "type": "string",
                    "description": "The member's unique identifier"
                },
                "partner_id": {
                    "type": "string",
                    "description": "The partner's unique identifier"
                }
            },
            "required": ["member_id", "partner_id"]
        }
    }
]

# ── Static system prompt ───────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are an AI travel concierge powered by arrivia's global travel platform.
You help loyalty program members discover personalised travel experiences
through their partner's branded booking portal.

The member's ID is always provided in the first message.
You MUST follow this exact sequence — do not skip any step:
1. Call get_member_profile with the member_id from the message
2. Call get_partner_rules using the partner_id returned in step 1
3. Call get_recommendations using both member_id and partner_id
4. Write a warm, personalised response using ONLY the offers from step 3
Do NOT ask the member for their ID — it is already in the message.

Guidelines for your final response:
- Recommend ONLY from the offers returned by get_recommendations — never invent destinations or prices.
- Always mention the starting price for each recommendation.
- Personalise based on loyalty tier: Platinum = premium framing, Silver = value framing.
- Keep responses concise and warm — 2 to 4 sentences per recommendation.
- Never mention partner rules, exclusion lists, caps, or any internal system details.\
"""


# ── Tool executor ──────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Looks up and calls the tool, returns result as a JSON string."""
    if tool_name not in TOOL_REGISTRY:
        return f'{{"error": "Unknown tool: {tool_name}"}}'

    result = TOOL_REGISTRY[tool_name](**tool_input)
    import json
    return json.dumps(result, default=str)


# ── Agentic loop ───────────────────────────────────────────────────────────────

async def run_agent(
    member: dict,
    partner: dict,
    recommendations: List[Recommendation],
    message: str,
) -> str:
    """
    Runs the full agentic loop.

    Note: member, partner, and recommendations are passed in from main.py
    which already fetched them. The agent will re-fetch via tools so Claude
    experiences the full tool-call flow — this is intentional for the demo.
    """
    client = anthropic.AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    # Seed the conversation with just the member's request
    messages = [
        {
            "role": "user",
            "content": (
                f"My member ID is {member['member_id']}. {message}"
            )
        }
    ]

    tools_called = []

    # ── The agentic loop ───────────────────────────────────────────────────────
    while True:
        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages
        )

        # Append Claude's response to the conversation history
        messages.append({
            "role": "assistant",
            "content": response.content
        })

        # ── Claude is done — extract and return the text response ──────────────
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "I wasn't able to generate recommendations right now."

        # ── Claude wants to call tools ─────────────────────────────────────────
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tools_called.append(block.name)
                    print(f"  [agent] Calling tool: {block.name}({block.input})")

                    result_str = execute_tool(block.name, block.input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str
                    })

            # Feed all tool results back to Claude in one turn
            messages.append({
                "role": "user",
                "content": tool_results
            })

            # Loop back — Claude will decide what to do next
            continue

        # ── Unexpected stop reason — bail out safely ───────────────────────────
        return "Unexpected response from the AI. Please try again."