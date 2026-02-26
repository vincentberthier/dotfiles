# Global Claude Code Preferences

This file contains global preferences that apply to all conversations and projects.

## Background Task Hygiene

**ALWAYS clean up behind yourself.** This is non-negotiable:

- **One task at a time.** Never launch overlapping background tasks that touch the same
  resource (hardware, ports, files).
- **Kill before launching.** Before starting any background process, check for and kill
  existing ones first (`pgrep`, then clean shutdown).
- **Kill when done.** The moment you're finished with a background process, stop it
  immediately. Never leave it running "for later."
- **Prefer foreground.** Only use background tasks when truly necessary. Default to
  synchronous execution.
- **Never fire-and-forget.** If you start it, you own it until it's dead.

## Delegation

Before spawning sub-agents or considering agent teams, load the `delegation` skill. Quick rules:

- Delegate self-contained, parallelizable work. Keep iterative/interactive work inline.
- Always inline full context into sub-agent prompts — they have no parent memory.
- Cap concurrent sub-agents at 5. Batch if more.
- Clean up: kill background agents the moment their work is done.

## Web Requests

When fetching documents from the web, use a timeout of at most one minute to prevent hangups if a resource doesn't load.

## File Deletion

Use `trash put` for all file and directory deletion. Use `trash restore --force` to restore. Never bypass deny rules with alternatives like `find -delete` or `unlink`.

## Bash Commands

Never prefix commands with `cd <dir> &&`. Use absolute paths and tool-native options instead.

## Coding

Scaffold if initializing a repo.

Often used scripts of more than a couple of lines should be persisted in dedicated scripts
or a Just recipe and their usage documented in the local CLAUDE.md and/or README.md (the
former if it'd only be useful for the agents, the latter if it's useful for the project).

<!-- BEGIN TYREX TEAM STANDARDS -->
## Tyrex Team Standards

These standards are managed by the Tyrex AI Agents repository. Do not edit this section
manually — it will be overwritten on the next install. Add personal preferences outside
the markers.

### Tone and Style

- Only use emojis if the user explicitly requests it.
- Avoid AI writing patterns: inflated significance ("crucial", "essential", "comprehensive"),
  copula avoidance ("serves as" instead of "is"), and rule-of-three overuse. Write with
  voice — have opinions, vary rhythm, be specific.
- Use plain, factual language. A bug fix is a bug fix, not a "critical stability improvement."
  Avoid: critical, crucial, essential, significant, comprehensive, robust, elegant.

### Asking Before Acting

When a request is ambiguous or underspecified, ask 1-5 clarifying questions before
implementing. Questions should eliminate whole branches of work. Offer multiple-choice
options with defaults. Support compact replies like `1b 2a 3c` or `defaults` to accept
all recommendations. Never run commands or edit files while waiting for answers — only
low-risk discovery reads are allowed.

### Philosophy

- **No speculative features** — Don't add features, flags, or configuration unless users
  actively need them.
- **No premature abstraction** — Don't create utilities until you've written the same code
  three times.
- **Clarity over cleverness** — Prefer explicit, readable code over dense one-liners.
- **Justify new dependencies** — Each dependency is attack surface and maintenance burden.
- **Replace, don't deprecate** — When a new implementation replaces an old one, remove the
  old one entirely. No backward-compatible shims or migration paths.
- **Verify at every level** — Set up automated guardrails (linters, type checkers, tests)
  as the first step, not an afterthought. Prefer structure-aware tools (ast-grep, LSPs,
  compilers) over text pattern matching.
- **Bias toward action** — Decide and move for anything easily reversed; state your
  assumption so the reasoning is visible. Ask before committing to interfaces, data
  models, architecture, or destructive operations.
- **Finish the job** — Handle edge cases you can see. Clean up what you touched. Flag
  broken adjacent code. But don't invent new scope.

### Code Quality

**Hard limits:** 100 lines per function max, cyclomatic complexity 8 max, 5 positional
parameters max.

**Zero warnings policy:** Fix every warning from every tool. If a warning truly can't be
fixed, add an inline ignore with a justification comment.

**Error handling:** Applications include context (what failed, what input, suggested fix).
Libraries return structured errors.

### Reviewing Code

Evaluate in order: architecture, code quality, tests, performance. For each issue: describe
with file:line references, present options with tradeoffs, recommend one, ask before
proceeding.

### Testing

- **Test edges and errors, not just the happy path.** Empty inputs, boundaries, malformed
  data, missing files, network failures — bugs live in edges.
- **Mock boundaries, not logic.** Only mock slow, non-deterministic, or external things.
- **Verify tests catch failures.** Break the code, confirm the test fails, then fix. Use
  mutation testing and property-based testing for parsers, serialization, and algorithms.

### Development

When writing code, load the relevant coding skill before starting. The skill contains the
full coding guide, TDD workflow, and validation commands.

When adding dependencies or tool versions, always look up the current stable version — never
assume from memory.

### Workflow

**One logical change per commit/changeset.** Every commit must build. Separate features,
fixes, refactoring, and documentation into separate commits.

**Before finalizing:** Re-read changes for unnecessary complexity. Run relevant tests. Run
linters and type checker — fix everything before finalizing.

**Merge request descriptions:** Describe what the code does now — not discarded approaches.
Use plain, factual language.

### Long-Running Tasks

For complex tasks requiring many tool calls, use file-based working memory to prevent
context drift. After every 2 search/read operations, save findings to disk. Re-read the
plan before major decisions.
<!-- END TYREX TEAM STANDARDS -->

