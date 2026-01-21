"""
AI query module for Claude Memory app.
Handles all Claude API interactions for semantic search and summarization.
Uses BYOK (Bring Your Own Key) - users provide their own API key.
"""

from typing import Optional
import anthropic

from .config import Config
from .database import search_entries
from . import constants


class AIQueryError(Exception):
    """Raised when AI query fails."""
    pass


class NoAPIKeyError(AIQueryError):
    """Raised when no API key is configured."""
    pass


def get_client() -> anthropic.Anthropic:
    """Get configured Anthropic client."""
    config = Config()
    if not config.ai_api_key:
        raise NoAPIKeyError(
            "No API key configured. Add your Anthropic API key to config.json"
        )
    return anthropic.Anthropic(api_key=config.ai_api_key)


def get_model_id() -> str:
    """Get the configured model ID."""
    config = Config()
    model_key = config.ai_model
    return constants.AI_MODELS.get(model_key, constants.AI_MODELS["claude-3-haiku"])


def format_memories_for_context(memories: list[dict]) -> str:
    """Format memory entries for inclusion in prompt."""
    if not memories:
        return "No relevant memories found."

    parts = []
    for i, mem in enumerate(memories, 1):
        entry = f"""--- Memory {i} ---
Title: {mem['title']}
Date: {mem['date']}
Category: {mem.get('category', 'uncategorized')}
Tags: {mem.get('tags', 'none')}

{mem['content']}
"""
        parts.append(entry)

    return "\n".join(parts)


def summarize_search_results(
    query: str,
    memories: list[dict],
    custom_instruction: Optional[str] = None,
) -> str:
    """
    Summarize search results using Claude.

    Args:
        query: The original search query
        memories: List of memory entries to summarize
        custom_instruction: Optional additional instructions

    Returns:
        AI-generated summary
    """
    if not memories:
        return "No memories found to summarize."

    client = get_client()
    model = get_model_id()

    memories_text = format_memories_for_context(memories)

    system_prompt = """You are an AI assistant helping to analyze and summarize personal memory/note entries.
Your task is to provide clear, organized summaries that help the user understand and find information in their notes.
Be concise but thorough. Group related information together. Cite specific entries when relevant."""

    user_prompt = f"""Search query: "{query}"

Here are the memory entries found:

{memories_text}

Please analyze these entries and provide:
1. A brief overall summary
2. Key themes or topics found (group related information)
3. Any notable insights or connections between entries

{custom_instruction or ''}"""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=constants.AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except anthropic.APIError as e:
        raise AIQueryError(f"API error: {e}")


def ask_memories(
    question: str,
    search_query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Ask a question about memories using AI.

    This is the main function for conversational memory search.
    It searches for relevant memories and uses Claude to answer the question.

    Args:
        question: Natural language question to answer
        search_query: Optional specific search terms (defaults to extracting from question)
        category: Optional category filter
        limit: Max memories to include in context

    Returns:
        AI-generated answer based on memories
    """
    client = get_client()
    model = get_model_id()

    # Search for relevant memories
    query = search_query or question
    memories = search_entries(query=query, category=category, limit=limit)

    if not memories:
        return f"I couldn't find any memories related to '{query}'. Try a different search term."

    memories_text = format_memories_for_context(memories)

    system_prompt = """You are an AI assistant with access to the user's personal memory/note database.
Answer questions based ONLY on the information in the provided memories.

IMPORTANT INSTRUCTIONS:
- Synthesize information from ALL relevant memories, not just one
- When multiple memories contain relevant info, combine them into a comprehensive answer
- Cite memories by their title (e.g., "In 'Tesla Investment Thesis'...")
- If memories contain different perspectives or details, include all of them
- If the memories don't contain enough information to answer, say so
- If asked to categorize or group information, do so clearly"""

    user_prompt = f"""Question: {question}

Here are the relevant memories from the database ({len(memories)} entries found):

{memories_text}

Please answer the question based on these memories."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=constants.AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except anthropic.APIError as e:
        raise AIQueryError(f"API error: {e}")


def chat_with_memories(
    messages: list[dict],
    memories: list[dict],
) -> str:
    """
    Multi-turn chat about memories.

    Args:
        messages: List of {"role": "user"|"assistant", "content": str}
        memories: Memory entries to use as context

    Returns:
        AI response
    """
    client = get_client()
    model = get_model_id()

    memories_text = format_memories_for_context(memories)

    # Build system prompt based on whether we have memories
    if memories:
        system_prompt = f"""You are a friendly, intelligent AI assistant helping the user explore their personal memory/note database.

You have access to {len(memories)} memories from their database (shown below). Use these to answer questions when relevant.

GUIDELINES:
- Be conversational and natural - you're a helpful assistant, not just a search tool
- When the user asks about topics in their memories, synthesize information across multiple entries
- Cite memories by title when referencing specific information (e.g., "In 'Tesla Investment Thesis'...")
- If memories contain different perspectives or details, include all of them
- If a question isn't about their memories, just have a normal helpful conversation
- You can discuss, analyze, or help with anything - memories are context, not a constraint

AVAILABLE MEMORIES:
{memories_text}"""
    else:
        system_prompt = """You are a friendly, intelligent AI assistant for a personal memory/note app.

Currently, no memories match the user's query. You can:
- Have a normal helpful conversation
- Suggest what kinds of things they might search for
- Help them think about what to save as memories
- Answer general questions

Be conversational and helpful - you're not limited to just memory search."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=constants.AI_MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
    except anthropic.APIError as e:
        raise AIQueryError(f"API error: {e}")
