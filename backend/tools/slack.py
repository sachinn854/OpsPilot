"""
Slack tool — post messages to channels.

The implementation here is mocked (no real Slack API call). A production
version would use slack_sdk with a SLACK_BOT_TOKEN from the environment.
"""
from backend.tools.base import Tool, ToolResult


class PostMessageTool(Tool):
    name = "slack_post_message"
    description = (
        "Post a message to a Slack channel. "
        "Use this to send reports, alerts, or summaries."
    )
    parameters = {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string",
                "description": "Channel name, e.g. '#ops' or '#alerts'.",
            },
            "text": {
                "type": "string",
                "description": "Message text (Markdown supported).",
            },
        },
        "required": ["channel", "text"],
    }

    async def run(self, channel: str, text: str) -> ToolResult:
        # Mocked — no real Slack API is called.
        return ToolResult(
            ok=True,
            data={
                "channel": channel,
                "text": text,
                "ts": "1700000000.000000",
                "note": "simulated (no real Slack API key configured)",
            },
        )
