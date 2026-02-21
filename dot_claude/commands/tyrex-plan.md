---
allowed-tools: Read, Glob, Grep, Write, WebFetch, Bash
description: Create an epic or issue plan interactively (&NNN, #NNN, or no argument for discovery)
---

Load the `tyrex-plans` skill and execute **Mode 1: Plan** with argument `$ARGUMENTS`.

The argument is one of:
- `&NNN` — plan an existing epic
- `#NNN` — plan an existing issue
- _(empty)_ — escalate the current conversation into a planned issue or epic (discovery flow)
