"""
Ops action tools (Phase 4) — *sensitive* actions used to demo HITL.

These represent real operational actions (rollback, restart) that change live
systems. They are intentionally marked sensitive (`sensitive = True`) so the
Security agent flags them and the run pauses for human approval before they run.

The implementations here are mocked (no real infra is touched) — they simulate
the action so the full HITL pause → approve → execute flow is demoable safely.
"""
from backend.tools.base import Tool, ToolResult

# Tool names the Security layer treats as sensitive (HITL required). Tools also
# advertise `sensitive = True`; this set is the static backstop the gate trusts.
SENSITIVE_TOOLS: set[str] = {"rollback_deployment", "restart_service"}


class RollbackDeploymentTool(Tool):
    name = "rollback_deployment"
    description = (
        "Roll back a service's deployment to its previous version. SENSITIVE: "
        "changes a live production system — requires human approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Name of the service to roll back (e.g. 'api').",
            },
        },
        "required": ["service"],
    }
    sensitive = True

    async def run(self, service: str) -> ToolResult:
        # Mocked action — no real infrastructure is touched.
        return ToolResult(
            ok=True,
            data={
                "service": service,
                "action": "rollback",
                "result": f"Rolled back '{service}' to the previous version (simulated).",
            },
        )


class RestartServiceTool(Tool):
    name = "restart_service"
    description = (
        "Restart a running service. SENSITIVE: disrupts a live system — "
        "requires human approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Name of the service to restart.",
            },
        },
        "required": ["service"],
    }
    sensitive = True

    async def run(self, service: str) -> ToolResult:
        return ToolResult(
            ok=True,
            data={
                "service": service,
                "action": "restart",
                "result": f"Restarted '{service}' (simulated).",
            },
        )
