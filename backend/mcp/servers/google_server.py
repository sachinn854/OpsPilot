from backend.mcp.adapter import MCPServer
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
from backend.tools.google_sheets import (
    SheetsAppendRowTool,
    SheetsClearRangeTool,
    SheetsCreateSpreadsheetTool,
    SheetsDeleteRowTool,
    SheetsGetInfoTool,
    SheetsReadRangeTool,
    SheetsUpdateCellTool,
)


class GoogleServer(MCPServer):
    name = "google"

    def tools(self):
        return [
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
        ]
