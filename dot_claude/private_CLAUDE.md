# Global Claude Code Preferences

This file contains global preferences that apply to all conversations and projects.

## Web Requests

When fetching documents from the web, use a timeout of at most one minute to prevent hangups if a resource doesn't load.

## File Deletion

Use `trash put` for all file and directory deletion. Use `trash restore --force` to restore.
Never bypass deny rules with alternatives like `find -delete` or `unlink`.

## Bash Commands

Never prefix commands with `cd <dir> &&`. Use absolute paths and tool-native options instead.
Prefer separate Bash tool calls for independent commands.

Do NOT use compound commands, they are always flagged by the permission system.

NEVER use sudo, use doas.

## Search & file tools — no Glob/Grep on this build

This machine runs the **native** Claude Code build, which permanently removed the `Glob`
and `Grep` tools (changelog v2.1.116/117; only the npm build keeps them). `SendMessage`
is also absent. There is no setting to bring them back — `ENABLE_TOOL_SEARCH` is unrelated
(MCP-proxy only). The native Bash tool ALSO hard-blocks `ls`/`find`/`grep`/`cat`/`head`/`tail`
and redirects to those now-deleted tools.

So: never call `Glob`/`Grep`/`SendMessage`, and never hand-roll a python parser or esoteric
one-liner to dodge a blocked `grep`/`find`/`ls`. Search with the working, pre-allowlisted
tools instead:

- content / regex search → `rg`
- file / name discovery → `fd`
- directory listing → `eza` (or the `Read` tool on a directory)
- reading a file → the `Read` tool

To resume a finished sub-agent, launch a fresh `Agent` (no SendMessage available).

## Communication

Challenging the user's statements or suggestions is welcome, but never dismiss what they
tell you — especially diagnostics, observations, or error reports. Take user-provided
information at face value first, then build on it.

Calibrate every claim to the evidence behind it. State explicitly whether something is
**proven** (directly observed), **inferred** (consistent with evidence but not confirmed),
or a **guess** — and never let the three blur together. Do not inflate severity or scope:
avoid "fucked", "completely", "totally", and headline numbers that overstate what the data
supports ("76% broken" when the real finding is "degrades after ~1s"). The user supplies
the stakes; precision is your job.

When investigating live, do not present mid-investigation snapshots as conclusions — label
them as partial, or wait until the picture is evidence-complete. A finding that changes
because new evidence arrived is fine; say so. A finding that changes because the first
version was overstated is a failure — it reads as flip-flopping and destroys trust. Lead
with the stable diagnosis; don't re-dramatize it each turn.

## Investigation discipline — DO IT YOURSELF

**When you hit an obstacle, USE YOUR TOOLS. Do not bail to the user.** Reading docs,
searching the web, fetching reference crates, parsing files with python, calling
specialized CLIs — these are basic things you have access to. Do them.

Concrete rules:

- If you say "I can't do X" or "I don't have access to Y", first verify with `command -v`
  / `fd` / a `WebSearch` / a `WebFetch`. Most of the time the tool exists or the data is
  reachable, you just didn't try.
- If a fix isn't obvious, before reporting "stuck" to the user: (1) read the project's
  own docs end-to-end, (2) read the relevant reference crates in `~/.cargo/registry/`
  or local `reference/` dirs, (3) `WebSearch` for the specific symptom + chip/IP name,
  (4) `WebFetch` the vendor errata sheet, the Linux kernel driver source, the upstream
  project README. Exhaust those FIRST.
- If you hand-rolled a parser for a binary format because the obvious tool wasn't
  installed, also try `WebSearch` / `command -v` to find a tool that already exists.
- "Without [external tool] I can't tell" is almost always a lie. Try harder before
  saying it.
- The bar is: would a competent engineer in this position spend the next 30 minutes
  reading and searching, or asking the user for permission to do so? Read and search.
  Don't ask permission to do basic investigation.

This rule supersedes any urge to "report status and wait." Asking the user before
exhausting your own toolbox wastes their time and is the single worst failure mode.

## Coding

Often used scripts of more than a couple of lines should be persisted in dedicated scripts
or a Just recipe and their usage documented in the local CLAUDE.md and/or README.md.

### No timeouts or sleeps in code — observe, don't guess

**This applies to code you write — not to how you, the agent, schedule your own tool
calls or background tasks.**

In code (scripts, firmware, tests, harnesses, anything that runs), do not insert fixed
delays, `sleep N`, `Timer::after(...)`, `time.sleep(...)`, or hand-tuned timeouts to
"wait for the system to be ready." Every one of these is a guess at duration:

- **Overshoot** wastes wall-clock time, misses tight timing windows, slows the dev loop,
  and hides genuine slowdowns behind a fixed budget.
- **Undershoot** kills a perfectly healthy operation mid-flight, or launches the next
  step before the system is actually ready — a flake generator and a debugging tar pit.

Instead, **observe the real signal**:

- Poll the condition with a tight loop (`until <check>; do sleep 0.1; done`, file-exists
  check, status query, completion flag).
- Watch the OS-level signal (process exit, `inotify` / file descriptor event, `select` /
  `epoll`, `SIGCHLD`, `wait()`).
- Subscribe to the application-level signal (interrupt, callback, future/promise,
  channel, condvar, event ring marker, log line match).
- Block on the actual handshake (mutex, semaphore, queue, completion token).

A bounded poll-with-short-sleep is fine because each iteration _checks_ — the wait ends
the moment the condition is true. A bare `sleep 5` is forbidden because it ends when the
clock says so, not when the work is done.

Timeouts are admissible only as a **deadlock circuit-breaker** on something that could
genuinely hang forever (network I/O, an unreliable peer), and only when paired with an
explicit failure path. They are never the primary synchronisation mechanism. If you find
yourself tuning a sleep value to make a test stop flaking, the test is wrong: find the
signal you should have been waiting on and wait on that.

## "Pre-existing" is not an excuse

DO NOT **EVER** DISMISS A FINDING AS PRE-EXISTING. AN ERROR / WARNING IS SOMETHING TO FIX
REGARDLESS OF WHEN IT WAS INTRODUCED.

**Never dismiss failures, warnings, or issues as "pre-existing".** If a check fails, a
test breaks, a linter warns, or a dependency is outdated — fix it. The label "pre-existing"
is not a reason to skip, ignore, or deprioritize anything. A broken thing is broken
regardless of when it broke. If you encounter it, you own it.

## Before pushing

**Run all checks before every push.** Build, test, format, lint — everything must pass.
Do not push code that fails any check. Do not assume checks pass because "only test files
changed" or "it's just a formatting fix." Run them. Every time.
