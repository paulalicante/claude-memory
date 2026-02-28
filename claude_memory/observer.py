"""
Observer module for Otterly Memory.

Inspired by Mastra's Observational Memory system, this module:
1. Periodically reviews conversation entries
2. Extracts condensed "observations" (key facts, preferences, decisions)
3. Creates "reflections" (patterns across observations)

This transforms raw conversation transcripts into actionable insights.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

import anthropic

from .config import Config
from . import database
from . import constants


class ObserverError(Exception):
    """Raised when observer fails."""
    pass


def get_client() -> anthropic.Anthropic:
    """Get configured Anthropic client."""
    config = Config()
    if not config.ai_api_key:
        raise ObserverError("No API key configured.")
    return anthropic.Anthropic(api_key=config.ai_api_key)


def get_todays_conversations(hours: int = 24) -> list[dict]:
    """
    Get conversation entries from the last N hours.

    Args:
        hours: How many hours back to look (default 24)

    Returns:
        List of conversation entries
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_str = cutoff.strftime('%Y-%m-%d')

    # Get all conversation entries from today
    entries = database.search_entries(
        query="",
        category="conversation",
        limit=100
    )

    # Filter to recent ones
    recent = []
    for entry in entries:
        entry_date = entry.get('date', '')
        if entry_date >= cutoff_str:
            recent.append(entry)

    return recent


def create_observation(conversations: list[dict]) -> Optional[str]:
    """
    Create an observation summary from conversations.

    Args:
        conversations: List of conversation entries to observe

    Returns:
        Observation text, or None if no meaningful observations
    """
    if not conversations:
        return None

    client = get_client()

    # Combine conversation content
    combined = []
    for conv in conversations:
        combined.append(f"--- {conv.get('title', 'Untitled')} ({conv.get('date', 'unknown date')}) ---\n{conv.get('content', '')}")

    conversations_text = "\n\n".join(combined)

    # Truncate if too long (keep under ~100K chars to stay within token limits)
    if len(conversations_text) > 100000:
        conversations_text = conversations_text[:100000] + "\n\n[... truncated ...]"

    system_prompt = """You are an observation agent for a personal memory system.

Your task is to extract OBSERVATIONS from conversations - condensed facts about:
- User preferences and working style
- Decisions made and their reasoning
- Technical knowledge and skill levels
- Projects being worked on and their status
- People, tools, and resources mentioned
- Problems encountered and solutions found
- Patterns in behavior or thinking

DO NOT just summarize the conversations. Extract FACTUAL OBSERVATIONS that would be useful for future context.

Format your response as a bulleted list of observations. Each observation should be:
- Specific and factual (not vague)
- Self-contained (understandable without the original conversation)
- Tagged with a category in brackets, e.g., [preference], [decision], [project], [technical], [person], [pattern]

Example output:
- [preference] User prefers dark theme UIs with Solarized color scheme
- [project] Working on "Mi Manitas" - a hyper-local help exchange app for Spain
- [technical] Uses PyQt6 for desktop GUI development, migrating from tkinter
- [decision] Chose to use Python subprocess for SQLite instead of Node native modules to avoid version mismatches
- [pattern] Tends to work on multiple projects simultaneously (5+ active)
- [person] Michelle (age 13) - user's daughter, interested in chemistry

If there are no meaningful observations to extract, respond with: NO_OBSERVATIONS"""

    user_prompt = f"""Here are the conversations from the last 24 hours:

{conversations_text}

Extract observations from these conversations."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # Use Sonnet for observation - good balance
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        result = response.content[0].text.strip()

        if result == "NO_OBSERVATIONS" or not result:
            return None

        return result

    except anthropic.APIError as e:
        raise ObserverError(f"API error during observation: {e}")


def create_reflection(observations: list[dict], days: int = 7) -> Optional[str]:
    """
    Create a reflection from recent observations.

    Reflections are higher-level patterns and insights derived from
    multiple observations over time.

    Args:
        observations: List of observation entries
        days: How many days of observations to consider

    Returns:
        Reflection text, or None if no meaningful reflection
    """
    if not observations:
        return None

    client = get_client()

    # Combine observation content
    combined = []
    for obs in observations:
        combined.append(f"--- {obs.get('date', 'unknown')} ---\n{obs.get('content', '')}")

    observations_text = "\n\n".join(combined)

    system_prompt = """You are a reflection agent for a personal memory system.

Your task is to identify PATTERNS and INSIGHTS across multiple daily observations.

Look for:
- Recurring themes or interests
- Evolution of projects over time
- Consistent preferences or working styles
- Skill development and learning patterns
- Relationship patterns (collaborators, tools, services)
- Potential opportunities or concerns

Format your response as:
1. **Key Patterns** - Recurring themes you've noticed
2. **Project Status** - Brief summary of active projects and their progress
3. **Insights** - Non-obvious connections or observations
4. **Recommendations** - Optional suggestions based on patterns

If there's nothing meaningful to reflect on, respond with: NO_REFLECTION"""

    user_prompt = f"""Here are the daily observations from the last {days} days:

{observations_text}

Create a reflection identifying patterns and insights."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        result = response.content[0].text.strip()

        if result == "NO_REFLECTION" or not result:
            return None

        return result

    except anthropic.APIError as e:
        raise ObserverError(f"API error during reflection: {e}")


def save_observation(content: str) -> int:
    """
    Save an observation to the database.

    Args:
        content: Observation text

    Returns:
        Entry ID
    """
    today = datetime.now().strftime('%Y-%m-%d')
    title = f"Daily Observations - {today}"

    return database.add_entry(
        title=title,
        content=content,
        category="observation",
        tags="auto-generated, observer, daily",
        source_conversation=json.dumps({
            "source": "observer",
            "type": "observation",
            "generated_at": datetime.now().isoformat()
        })
    )


def save_reflection(content: str, period_days: int = 7) -> int:
    """
    Save a reflection to the database.

    Args:
        content: Reflection text
        period_days: How many days this reflection covers

    Returns:
        Entry ID
    """
    today = datetime.now().strftime('%Y-%m-%d')
    title = f"Weekly Reflection - {today}"

    return database.add_entry(
        title=title,
        content=content,
        category="reflection",
        tags=f"auto-generated, observer, {period_days}-day",
        source_conversation=json.dumps({
            "source": "observer",
            "type": "reflection",
            "period_days": period_days,
            "generated_at": datetime.now().isoformat()
        })
    )


def run_daily_observer() -> dict:
    """
    Run the daily observation process.

    1. Gets conversations from last 24 hours
    2. Creates observations
    3. Saves to database

    Returns:
        Status dict with results
    """
    result = {
        "conversations_found": 0,
        "observation_created": False,
        "observation_id": None,
        "error": None
    }

    try:
        # Get recent conversations
        conversations = get_todays_conversations(hours=24)
        result["conversations_found"] = len(conversations)

        if not conversations:
            result["error"] = "No conversations found in last 24 hours"
            return result

        # Create observation
        observation = create_observation(conversations)

        if not observation:
            result["error"] = "No meaningful observations extracted"
            return result

        # Save observation
        entry_id = save_observation(observation)
        result["observation_created"] = True
        result["observation_id"] = entry_id

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


def run_weekly_reflection() -> dict:
    """
    Run the weekly reflection process.

    1. Gets observations from last 7 days
    2. Creates reflection
    3. Saves to database

    Returns:
        Status dict with results
    """
    result = {
        "observations_found": 0,
        "reflection_created": False,
        "reflection_id": None,
        "error": None
    }

    try:
        # Get recent observations
        observations = database.search_entries(
            query="",
            category="observation",
            limit=14  # Up to 2 weeks worth
        )

        # Filter to last 7 days
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        recent_obs = [o for o in observations if o.get('date', '') >= cutoff]
        result["observations_found"] = len(recent_obs)

        if not recent_obs:
            result["error"] = "No observations found in last 7 days"
            return result

        # Create reflection
        reflection = create_reflection(recent_obs, days=7)

        if not reflection:
            result["error"] = "No meaningful reflection generated"
            return result

        # Save reflection
        entry_id = save_reflection(reflection, period_days=7)
        result["reflection_created"] = True
        result["reflection_id"] = entry_id

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


# CLI interface for manual/scheduled runs
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m claude_memory.observer [observe|reflect|both]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command in ("observe", "both"):
        print("Running daily observer...")
        result = run_daily_observer()
        print(f"  Conversations found: {result['conversations_found']}")
        if result['observation_created']:
            print(f"  Observation saved: ID {result['observation_id']}")
        else:
            print(f"  No observation: {result['error']}")

    if command in ("reflect", "both"):
        print("Running weekly reflection...")
        result = run_weekly_reflection()
        print(f"  Observations found: {result['observations_found']}")
        if result['reflection_created']:
            print(f"  Reflection saved: ID {result['reflection_id']}")
        else:
            print(f"  No reflection: {result['error']}")

    if command not in ("observe", "reflect", "both"):
        print(f"Unknown command: {command}")
        print("Usage: python -m claude_memory.observer [observe|reflect|both]")
        sys.exit(1)
