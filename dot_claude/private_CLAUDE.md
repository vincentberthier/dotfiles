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

## Communication

Challenging the user's statements or suggestions is welcome, but never dismiss what they
tell you — especially diagnostics, observations, or error reports. Take user-provided
information at face value first, then build on it.

## Coding

Often used scripts of more than a couple of lines should be persisted in dedicated scripts
or a Just recipe and their usage documented in the local CLAUDE.md and/or README.md.

## "Pre-existing" is not an excuse

**Never dismiss failures, warnings, or issues as "pre-existing".** If a check fails, a
test breaks, a linter warns, or a dependency is outdated — fix it. The label "pre-existing"
is not a reason to skip, ignore, or deprioritize anything. A broken thing is broken
regardless of when it broke. If you encounter it, you own it.
