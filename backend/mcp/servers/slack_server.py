from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.slack import (
    SlackAddReactionTool,
    SlackCreateChannelTool,
    SlackDeleteMessageTool,
    SlackGetMessagesTool,
    SlackGetThreadTool,
    SlackGetUserInfoTool,
    SlackInviteToChannelTool,
    SlackListChannelsTool,
    SlackListUsersTool,
    SlackPinMessageTool,
    SlackPostMessageTool,
    SlackScheduleMessageTool,
    SlackSearchMessagesTool,
    SlackSendDMTool,
    SlackSetTopicTool,
    SlackUpdateMessageTool,
    SlackUploadFileTool,
)


class SlackServer(MCPServer):
    name = "slack"

    def tools(self) -> list[Tool]:
        return [
            # Read tools
            SlackPostMessageTool(),
            SlackListChannelsTool(),
            SlackGetMessagesTool(),
            SlackGetThreadTool(),
            SlackSendDMTool(),
            SlackSearchMessagesTool(),
            SlackGetUserInfoTool(),
            SlackListUsersTool(),
            SlackAddReactionTool(),
            SlackUploadFileTool(),
            # Write tools (sensitive — HITL)
            SlackCreateChannelTool(),
            SlackSetTopicTool(),
            SlackInviteToChannelTool(),
            SlackUpdateMessageTool(),
            SlackDeleteMessageTool(),
            SlackPinMessageTool(),
            SlackScheduleMessageTool(),
        ]
