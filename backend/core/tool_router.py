"""
Tool Router.

A small registry that:
  - holds the available tools,
  - exposes their schemas to the LLM,
  - dispatches a tool call by name to the right tool.

Agents talk to this, never to a concrete tool. Later an MCP adapter plugs
in here so tools can be discovered over the protocol — no agent changes needed.
"""
from backend.tools.base import Tool, ToolResult


class ToolRouter:
    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        self._schema_cache: list[dict] | None = None
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        self._schema_cache = None  # invalidate on change

    def schemas(self) -> list[dict]:
        """All tool schemas in OpenAI/Groq function-calling format."""
        if self._schema_cache is None:
            self._schema_cache = [tool.to_openai_schema() for tool in self._tools.values()]
        return self._schema_cache

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, error=f"Unknown tool: {name}")
        try:
            return await tool.run(**arguments)
        except TypeError as exc:
            # Wrong/missing arguments from the model.
            return ToolResult(ok=False, error=f"Bad arguments for '{name}': {exc}")


def build_default_router() -> "ToolRouter":
    """The standard tool set used by the Copilot and the multi-agent runs.

    Kept in one place so every entrypoint exposes the same tools. As tools move
    to MCP, only this factory changes.
    """
    from backend.tools.github import (
        GitHubAddLabelsTool,
        GitHubBranchesTool,
        GitHubCloseIssueTool,
        GitHubClosePRTool,
        GitHubCommentOnIssueTool,
        GitHubCommentOnPRTool,
        GitHubCompareBranchesTool,
        GitHubCommitsTool,
        GitHubContributorsTool,
        GitHubCreateBranchTool,
        GitHubCreateIssueTool,
        GitHubCreatePRTool,
        GitHubFileContentTool,
        GitHubFileTreeTool,
        GitHubGetIssueTool,
        GitHubGetPRTool,
        GitHubGetTagsTool,
        GitHubIssuesTool,
        GitHubListMilestonesTool,
        GitHubListWorkflowsTool,
        GitHubMergePRTool,
        GitHubPRsTool,
        GitHubReadmeTool,
        GitHubReleasesTool,
        GitHubRepoInfoTool,
        GitHubRepoLanguagesTool,
        GitHubSearchCodeTool,
        GitHubUpdateIssueTool,
        GitHubUserReposTool,
        GitHubWorkflowRunsTool,
    )
    from backend.tools.ops import RestartServiceTool, RollbackDeploymentTool
    from backend.tools.rag import RagSearchTool
    from backend.tools.workflows import (
        BroadcastIncidentTool,
        GenerateStandupTool,
        NotifyPRStakeholdersTool,
        NotifyStalePRsTool,
    )
    from backend.tools.utils import CalculatorTool, DateTimeTool, TimezoneConverterTool
    from backend.tools.web_search import WebSearchTool
    from backend.tools.google_gmail import (
        GmailCreateDraftTool,
        GmailForwardEmailTool,
        GmailGetEmailTool,
        GmailListEmailsTool,
        GmailListLabelsTool,
        GmailMarkReadTool,
        GmailReplyEmailTool,
        GmailSearchEmailsTool,
        GmailSendEmailTool,
        GmailTrashEmailTool,
    )
    from backend.tools.google_calendar import (
        CalendarCreateEventTool,
        CalendarCreateMeetingTool,
        CalendarDeleteEventTool,
        CalendarFindFreeSlotTool,
        CalendarGetEventTool,
        CalendarListEventsTool,
        CalendarUpdateEventTool,
    )
    from backend.tools.google_drive import (
        DriveCreateFolderTool,
        DriveDeleteFileTool,
        DriveGetFileTool,
        DriveListFolderTool,
        DriveMoveFileTool,
        DriveReadFileTool,
        DriveSearchFilesTool,
        DriveShareFileTool,
    )
    from backend.tools.google_sheets import (
        SheetsAppendRowTool,
        SheetsClearRangeTool,
        SheetsCreateSpreadsheetTool,
        SheetsDeleteRowTool,
        SheetsGetInfoTool,
        SheetsReadRangeTool,
        SheetsUpdateCellTool,
    )
    from backend.tools.jira import (
        JiraAddCommentTool,
        JiraCreateIssueTool,
        JiraGetCommentsTool,
        JiraGetIssueTool,
        JiraGetIssuesTool,
        JiraGetProjectsTool,
        JiraTransitionIssueTool,
        JiraUpdateIssueTool,
    )
    from backend.tools.linear import (
        LinearAddCommentTool,
        LinearCreateIssueTool,
        LinearGetIssueTool,
        LinearGetIssuesTool,
        LinearGetProjectsTool,
        LinearGetTeamsTool,
        LinearUpdateIssueTool,
    )
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
    from backend.tools.notion import (
        NotionAppendBlockTool,
        NotionCreatePageTool,
        NotionGetPageContentTool,
        NotionGetPageTool,
        NotionQueryDatabaseTool,
        NotionSearchTool,
        NotionUpdatePageTool,
    )
    from backend.tools.confluence import (
        ConfluenceCreatePageTool,
        ConfluenceGetPageTool,
        ConfluenceGetSpacePagesTool,
        ConfluenceListSpacesTool,
        ConfluenceSearchTool,
        ConfluenceUpdatePageTool,
    )
    from backend.tools.pagerduty import (
        PagerDutyAcknowledgeIncidentTool,
        PagerDutyCreateIncidentTool,
        PagerDutyGetIncidentTool,
        PagerDutyGetOncallTool,
        PagerDutyListIncidentsTool,
        PagerDutyListServicesTool,
        PagerDutyResolveIncidentTool,
    )
    from backend.tools.hubspot import (
        HubSpotCreateContactTool,
        HubSpotCreateDealTool,
        HubSpotGetContactTool,
        HubSpotGetDealTool,
        HubSpotListCompaniesTool,
        HubSpotListDealsTool,
        HubSpotSearchContactsTool,
        HubSpotUpdateContactTool,
    )

    return ToolRouter(
        [
            # GitHub read tools
            GitHubRepoInfoTool(),
            GitHubReadmeTool(),
            GitHubFileTreeTool(),
            GitHubFileContentTool(),
            GitHubReleasesTool(),
            GitHubContributorsTool(),
            GitHubBranchesTool(),
            GitHubSearchCodeTool(),
            GitHubUserReposTool(),
            GitHubRepoLanguagesTool(),
            GitHubIssuesTool(),
            GitHubGetIssueTool(),
            GitHubPRsTool(),
            GitHubGetPRTool(),
            GitHubCommitsTool(),
            GitHubListWorkflowsTool(),
            GitHubWorkflowRunsTool(),
            GitHubCompareBranchesTool(),
            GitHubGetTagsTool(),
            GitHubListMilestonesTool(),
            # GitHub write tools (sensitive — HITL)
            GitHubCreateIssueTool(),
            GitHubUpdateIssueTool(),
            GitHubCloseIssueTool(),
            GitHubAddLabelsTool(),
            GitHubCommentOnIssueTool(),
            GitHubCreatePRTool(),
            GitHubMergePRTool(),
            GitHubClosePRTool(),
            GitHubCommentOnPRTool(),
            GitHubCreateBranchTool(),
            # Slack read tools
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
            # Slack write tools (sensitive — HITL)
            SlackCreateChannelTool(),
            SlackSetTopicTool(),
            SlackInviteToChannelTool(),
            SlackUpdateMessageTool(),
            SlackDeleteMessageTool(),
            SlackPinMessageTool(),
            SlackScheduleMessageTool(),
            # Gmail read
            GmailListEmailsTool(),
            GmailGetEmailTool(),
            GmailSearchEmailsTool(),
            GmailListLabelsTool(),
            GmailMarkReadTool(),
            # Gmail write (sensitive)
            GmailSendEmailTool(),
            GmailReplyEmailTool(),
            GmailForwardEmailTool(),
            GmailCreateDraftTool(),
            GmailTrashEmailTool(),
            # Calendar read
            CalendarListEventsTool(),
            CalendarGetEventTool(),
            CalendarFindFreeSlotTool(),
            # Calendar write (sensitive)
            CalendarCreateEventTool(),
            CalendarCreateMeetingTool(),
            CalendarUpdateEventTool(),
            CalendarDeleteEventTool(),
            # Drive read
            DriveSearchFilesTool(),
            DriveListFolderTool(),
            DriveGetFileTool(),
            DriveReadFileTool(),
            # Drive write (sensitive)
            DriveCreateFolderTool(),
            DriveShareFileTool(),
            DriveMoveFileTool(),
            DriveDeleteFileTool(),
            # Sheets read
            SheetsGetInfoTool(),
            SheetsReadRangeTool(),
            # Sheets write (sensitive)
            SheetsAppendRowTool(),
            SheetsUpdateCellTool(),
            SheetsCreateSpreadsheetTool(),
            SheetsClearRangeTool(),
            SheetsDeleteRowTool(),
            # Jira read tools
            JiraGetProjectsTool(),
            JiraGetIssuesTool(),
            JiraGetIssueTool(),
            JiraGetCommentsTool(),
            # Jira write tools (sensitive — HITL)
            JiraCreateIssueTool(),
            JiraUpdateIssueTool(),
            JiraAddCommentTool(),
            JiraTransitionIssueTool(),
            # Linear read tools
            LinearGetTeamsTool(),
            LinearGetIssuesTool(),
            LinearGetIssueTool(),
            LinearGetProjectsTool(),
            # Linear write tools (sensitive — HITL)
            LinearCreateIssueTool(),
            LinearUpdateIssueTool(),
            LinearAddCommentTool(),
            # RAG
            RagSearchTool(),
            # Ops (sensitive — HITL)
            RollbackDeploymentTool(),
            RestartServiceTool(),
            # Utility tools
            CalculatorTool(),
            DateTimeTool(),
            TimezoneConverterTool(),
            WebSearchTool(),
            # Cross-service workflows
            GenerateStandupTool(),
            NotifyStalePRsTool(),
            BroadcastIncidentTool(),
            NotifyPRStakeholdersTool(),
            # Notion read
            NotionSearchTool(),
            NotionGetPageTool(),
            NotionGetPageContentTool(),
            NotionQueryDatabaseTool(),
            # Notion write (sensitive)
            NotionCreatePageTool(),
            NotionUpdatePageTool(),
            NotionAppendBlockTool(),
            # Confluence read
            ConfluenceSearchTool(),
            ConfluenceGetPageTool(),
            ConfluenceListSpacesTool(),
            ConfluenceGetSpacePagesTool(),
            # Confluence write (sensitive)
            ConfluenceCreatePageTool(),
            ConfluenceUpdatePageTool(),
            # PagerDuty read
            PagerDutyListIncidentsTool(),
            PagerDutyGetIncidentTool(),
            PagerDutyListServicesTool(),
            PagerDutyGetOncallTool(),
            # PagerDuty write (sensitive)
            PagerDutyCreateIncidentTool(),
            PagerDutyAcknowledgeIncidentTool(),
            PagerDutyResolveIncidentTool(),
            # HubSpot read
            HubSpotSearchContactsTool(),
            HubSpotGetContactTool(),
            HubSpotListDealsTool(),
            HubSpotGetDealTool(),
            HubSpotListCompaniesTool(),
            # HubSpot write (sensitive)
            HubSpotCreateContactTool(),
            HubSpotUpdateContactTool(),
            HubSpotCreateDealTool(),
        ]
    )


def sensitive_tool_names(router: "ToolRouter") -> set[str]:
    """Names of tools in `router` that require human approval before running."""
    return {
        name
        for name, tool in router._tools.items()
        if getattr(tool, "sensitive", False)
    }
