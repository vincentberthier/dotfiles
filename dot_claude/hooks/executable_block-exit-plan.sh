#!/bin/bash
# Block agent-initiated ExitPlanMode calls.
# The user exits plan mode manually when ready.

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Do NOT exit plan mode. Present the plan and wait for user feedback. The user will exit plan mode manually when ready to proceed."
    }
  }
}
EOF
