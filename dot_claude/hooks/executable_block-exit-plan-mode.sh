#!/usr/bin/env bash
# Block ExitPlanMode — the user decides when to leave plan mode, not the agent.
cat <<'EOF'
{"decision": "block", "reason": "Do NOT exit plan mode. The user will exit plan mode themselves when ready. Never call ExitPlanMode or suggest exiting plan mode."}
EOF
