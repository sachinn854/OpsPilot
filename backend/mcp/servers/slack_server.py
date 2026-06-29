from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.slack import (
    SlackCreateChannelTool,
    SlackGetMessagesTool,
    SlackGetUserInfoTool,
    SlackListChannelsTool,
    SlackPostMessageTool,
    SlackSearchMessagesTool,
    SlackSendDMTool,
    SlackSetTopicTool,
    SlackUploadFileTool,
)


class SlackServer(MCPServer):
    name = "slack"

    def tools(self) -> list[Tool]:
        return [
            SlackPostMessageTool(),
            SlackListChannelsTool(),
            SlackGetMessagesTool(),
            SlackSendDMTool(),
            SlackSearchMessagesTool(),
            SlackGetUserInfoTool(),
            SlackUploadFileTool(),
            SlackCreateChannelTool(),
            SlackSetTopicTool(),
        ]
