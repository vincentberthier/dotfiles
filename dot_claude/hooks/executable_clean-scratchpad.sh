#!/usr/bin/env bash
# SessionEnd hook: remove this session's scratchpad directory.
#
# Claude Code never cleans up its own scratchpad. Left alone, sessions that
# write large intermediates (astro stacks, build artifacts) accumulate
# indefinitely under $CLAUDE_CODE_TMPDIR/claude-$UID/<project-slug>/<session-id>/.
#
# Layout:  <root>/<project-slug>/<session-id>/{scratchpad,tasks,...}
# We remove the whole <session-id> directory.
#
# Skipped when the session ends via /clear: the session id survives a clear,
# so its scratchpad is still live working state.

set -euo pipefail

payload="$(cat)"
reason="$(jq -r '.reason // empty' <<<"$payload" 2>/dev/null || true)"
[[ "$reason" == "clear" ]] && exit 0

sid="${CLAUDE_CODE_SESSION_ID:-}"
root="${CLAUDE_CODE_TMPDIR:-/tmp}/claude-$(id -u)"

# Refuse to act on anything we cannot fully pin down.
[[ -n "$sid" ]] || exit 0
[[ "$sid" =~ ^[0-9a-fA-F-]{36}$ ]] || exit 0
[[ -d "$root" ]] || exit 0

# Session dirs live exactly one level below the root, named for the UUID.
while IFS= read -r dir; do
    [[ -n "$dir" ]] || continue
    resolved="$(realpath -- "$dir")"

    # Hard guard: must be <root>/<one-segment>/<sid>, nothing else.
    [[ "$resolved" == "$root"/*/"$sid" ]] || continue
    [[ "$(basename -- "$resolved")" == "$sid" ]] || continue

    rm -rf -- "$resolved"
done < <(fd --type d --min-depth 2 --max-depth 2 --absolute-path "^${sid}$" "$root" 2>/dev/null || true)

exit 0
