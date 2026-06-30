"""
Slack Socket Mode bot — bidirectional integration.

Listens for:
  - Direct messages to the bot
  - @mentions of the bot in any channel

On each event, runs the message through CopilotAgent and replies in Slack.

Also processes active SlackEventTriggers — when a message matches a trigger
keyword in the watched channel, runs the configured action automatically.

Start alongside the main app:
    python -m backend.workers.slack_bot

Requires in .env:
    SLACK_TOKEN     = xoxb-...   (Bot User OAuth Token)
    SLACK_APP_TOKEN = xapp-...   (App-Level Token with connections:write scope)

In your Slack app settings:
    1. Enable Socket Mode (Settings → Socket Mode)
    2. Generate an App-Level Token with connections:write scope
    3. Under Event Subscriptions → Subscribe to bot events:
         message.im       (DMs to the bot)
         app_mention      (@mentions in channels)
"""
import asyncio
import json
import logging
import os
import re

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from backend.config import settings

logger = logging.getLogger("copilot.slack_bot")

app = AsyncApp(token=settings.SLACK_TOKEN, ignoring_self_events=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def _strip_mention(text: str) -> str:
    """Remove <@BOTID> mention prefix from message text."""
    return re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()


async def _run_copilot(user_message: str, org_id: str) -> str:
    """Run a message through CopilotAgent and return the reply text."""
    from backend.core.tool_router import build_default_router
    from backend.llm.openrouter_provider import OpenRouterProvider
    from backend.agents.copilot import CopilotAgent

    llm    = OpenRouterProvider()
    router = build_default_router()
    agent  = CopilotAgent(llm, router)

    history = [{"role": "user", "content": user_message}]
    try:
        reply = await agent.run(history)
        return reply or "I couldn't generate a response."
    except Exception as exc:
        logger.error("CopilotAgent error: %s", exc)
        return f"Sorry, I ran into an error: {exc}"


async def _run_event_trigger_action(trigger, message_text: str, channel_name: str) -> None:
    """Execute the action configured on a SlackEventTrigger."""
    config = json.loads(trigger.action_config or "{}")

    if trigger.action_type == "create_github_issue":
        repo  = config.get("repo", "")
        label = config.get("label", "slack-trigger")
        if not repo:
            logger.warning("Event trigger %s has no repo configured", trigger.id)
            return
        from backend.tools.github import GitHubCreateIssueTool
        tool = GitHubCreateIssueTool()
        await tool.run(
            repo=repo,
            title=f"[Slack trigger] {message_text[:80]}",
            body=(
                f"**Triggered by keyword:** `{trigger.trigger_keyword}`\n"
                f"**Channel:** #{channel_name}\n\n"
                f"**Message:**\n{message_text}"
            ),
            labels=[label],
            org_id=trigger.org_id,
        )

    elif trigger.action_type == "post_to_channel":
        target = config.get("channel", "")
        msg    = config.get("message", "").replace("{text}", message_text) \
                 or f"Trigger fired in #{channel_name}: {message_text[:200]}"
        if not target:
            return
        from backend.tools.slack import SlackPostMessageTool
        await SlackPostMessageTool().run(channel=target, text=msg, org_id=trigger.org_id)

    elif trigger.action_type == "run_copilot":
        prompt = config.get("prompt", message_text)
        reply  = await _run_copilot(prompt, trigger.org_id)
        target = config.get("reply_channel", "") or channel_name
        from backend.tools.slack import SlackPostMessageTool
        await SlackPostMessageTool().run(channel=target, text=reply, org_id=trigger.org_id)


# ── event handlers ────────────────────────────────────────────────────────────

@app.event("message")
async def handle_dm(event, say, client):
    """Handle direct messages sent to the bot."""
    # Only process DMs (channel_type == "im") and skip bot messages
    if event.get("channel_type") != "im":
        return
    if event.get("bot_id") or event.get("subtype"):
        return

    user_text = (event.get("text") or "").strip()
    if not user_text:
        return

    org_id = event.get("user", "default")
    logger.info("Slack DM from %s: %s", org_id, user_text[:80])

    await say("_Thinking…_")
    reply = await _run_copilot(user_text, org_id)
    await say(reply)


@app.event("app_mention")
async def handle_mention(event, say, client):
    """Handle @bot mentions in channels."""
    if event.get("bot_id"):
        return

    user_text = _strip_mention(event.get("text") or "")
    if not user_text:
        await say("Hi! How can I help? Just ask me anything.")
        return

    org_id = event.get("user", "default")
    logger.info("Slack mention from %s: %s", org_id, user_text[:80])

    await say("_On it…_", thread_ts=event.get("ts"))
    reply = await _run_copilot(user_text, org_id)
    await say(reply, thread_ts=event.get("ts"))

    # Also check event triggers for mentions
    await _check_triggers(user_text, event.get("channel", ""), org_id, client)


@app.event("message")
async def handle_channel_message(event, say, client):
    """Watch channel messages for event trigger keywords."""
    if event.get("channel_type") == "im":
        return  # handled by handle_dm
    if event.get("bot_id") or event.get("subtype"):
        return

    text    = (event.get("text") or "").strip()
    channel = event.get("channel", "")
    user    = event.get("user", "default")
    if text:
        await _check_triggers(text, channel, user, client)


async def _check_triggers(text: str, channel_id: str, org_id: str, client) -> None:
    """Check active event triggers against a message and fire matching ones."""
    try:
        from sqlalchemy import select
        from backend.db.models import SlackEventTrigger
        from backend.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            triggers = (await session.execute(
                select(SlackEventTrigger).where(SlackEventTrigger.is_active == True)  # noqa: E712
            )).scalars().all()

        text_lower = text.lower()

        # Resolve channel name for filtering
        channel_name = channel_id
        try:
            info = await client.conversations_info(channel=channel_id)
            channel_name = info["channel"].get("name", channel_id)
        except Exception:
            pass

        for trigger in triggers:
            if trigger.trigger_keyword not in text_lower:
                continue
            if trigger.source_channel and trigger.source_channel != channel_name:
                continue
            logger.info("Event trigger '%s' fired on keyword '%s'",
                        trigger.name, trigger.trigger_keyword)
            asyncio.create_task(_run_event_trigger_action(trigger, text, channel_name))

    except Exception as exc:
        logger.error("Error checking event triggers: %s", exc)


# ── entrypoint ────────────────────────────────────────────────────────────────

async def start_bot() -> None:
    if not settings.SLACK_TOKEN:
        logger.error("SLACK_TOKEN not set — Slack bot cannot start")
        return
    if not settings.SLACK_APP_TOKEN:
        logger.error("SLACK_APP_TOKEN not set — Socket Mode requires an App-Level Token")
        return
    handler = AsyncSocketModeHandler(app, settings.SLACK_APP_TOKEN)
    logger.info("Starting Slack Socket Mode bot…")
    await handler.start_async()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_bot())
