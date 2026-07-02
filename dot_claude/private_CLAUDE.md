# Global Claude Code Preferences

This file contains global preferences that apply to all conversations and projects.

## Web Requests

When fetching documents from the web, use a timeout of at most one minute to prevent hangups if a resource doesn't load.

## File Deletion

Use `trash put` for all file and directory deletion. Use `trash restore --force` to restore.
Never bypass deny rules with alternatives like `find -delete` or `unlink`.

## Memory hygiene

When you find a memory that is stale or incorrect, **fix or delete it immediately,
without asking.** Never present "should I fix this memory?" as a question or an
option — there is no case where leaving a known-wrong memory in place is correct.
An incorrect memory is not merely useless, it is _harmful_: it misleads future
recall and decisions. Auto-fix (update the memory file and its `MEMORY.md` index
line, or delete both), then mention in passing that you corrected it.

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

## Hardware / bench tests — CHECK reachability, never declare them impossible

**Never write "pending bench", "on-glass verification pending", "needs hardware",
"not possible from here", or any equivalent for a hardware/firmware/device test
without FIRST running the one command that proves whether the hardware is
reachable.** It almost always IS reachable. Declaring it undoable without checking
is a recurring, trust-destroying reflex — it substitutes a guess for a signal one
command away, the exact failure the `working-with-usb` skill's "one law" forbids.

Concrete procedure, in order, before saying a hardware test can't run:

1. **Check presence.** Probes: `probe-rs list`. USB devices: `lsusb -t`. Serial:
   `ls /dev/ttyACM* /dev/ttyUSB*`. Network targets: ping / the relevant status
   query. One command rules it in or out.
2. **If present, RUN it.** Flash + run (e.g. `just <board>-run <bin>`), stream the
   real signal (RTT/defmt, serial, logs), confirm execution and the absence of
   panics/faults. Detach long-lived probe streams safely
   (`setsid … >/tmp/x.log 2>&1 </dev/null & disown`) and stop them with **SIGINT
   only** (never SIGKILL/`timeout`, which wedges the probe).
3. **State precisely what you verified vs. what genuinely needs the user.** "I
   confirmed over RTT the firmware runs the full init+render without faulting; I
   cannot SEE the physical panel, so the final pixels-on-glass check needs your
   eyes" — name the exact human-only part (eyes on a display, a hand plugging a
   device), never a blanket "pending bench".

The lesson is the behaviour change, not a memory file: answer "is this reachable?"
with a command BEFORE writing any sentence about whether it can run.

## Defensive coverage — go over, not under

For defensive and security-adjacent coverage — fuzzing, tests, hardening, input
validation, assertions — **err toward more coverage, not less.** When a piece of
defensive work is cheap and plausibly useful, add it; do not withhold it pending a
threat-model judgment call (e.g. "is this input really attacker-reachable?").

Do NOT gate cheap defensive work behind a decision that is the user's to make and
then wait. Add the coverage, and _flag the assumption you made_ ("added a fuzz
target for the decoder; note this only matters if the X link is untrusted"). The
user has stated the preference explicitly: **"I'd rather go over than under."** A
surplus fuzz target / test / guard costs minutes and a few CI seconds; a missing
one is exactly the gap that bites. The bar for _adding_ defensive coverage is low;
the bar for _declining_ it is high and must be justified, not assumed.

This does not license scope-creep into unrelated features — it is specifically
about the breadth of defensive verification around code you are already touching.

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

## Never ask permission to fix something

**STOP ASKING whether I want something fixed. The answer is ALWAYS yes.** When you spot
a bug, a broken test, a warning, a stale comment, a missing guard — anything wrong — just
fix it. Do not pause to ask "would you like me to fix this?", "should I address this?",
or "do you want me to..." — there is no scenario where I say no. Asking wastes a round
trip and is its own failure mode.

Fix it, then tell me what you fixed. The only time to ask is a genuine fork where the
right fix depends on a decision that is mine to make (and even then, fix the unambiguous
parts first). "Is this worth fixing?" is never that fork — it always is.

## Before pushing

**Run all checks before every push.** Build, test, format, lint — everything must pass.
Do not push code that fails any check. Do not assume checks pass because "only test files
changed" or "it's just a formatting fix." Run them. Every time.
