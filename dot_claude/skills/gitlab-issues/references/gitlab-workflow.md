# GitLab Workflow Reference

This reference provides a comprehensive guide to using the `glab` CLI tool for GitLab issue and merge request management.

## Table of Contents

- [Authentication](#authentication)
- [Issue Commands](#issue-commands)
- [Merge Request Commands](#merge-request-commands)
- [Label Management](#label-management)
- [Milestone Management](#milestone-management)
- [CI/CD](#cicd)
- [Repository](#repository)
- [Tips for Effective Issues](#tips-for-effective-issues)
- [Linking Issues and MRs](#linking-issues-and-mrs)

---

## Authentication

### Login

```bash
# Interactive login (recommended)
glab auth login

# Login with a token
glab auth login --token <personal-access-token>

# Login to a self-hosted instance
glab auth login --hostname gitlab.example.com
```

### Status

```bash
# Check authentication status
glab auth status
```

Expected output when authenticated:

```
gitlab.com
  Token: ********
  Git Protocol: ssh
  API URL: https://gitlab.com/api/v4
```

---

## Issue Commands

### Listing Issues

```bash
# List open issues
glab issue list

# List closed issues
glab issue list --closed

# List all issues (open and closed)
glab issue list --all

# Filter by label
glab issue list --label "bug"
glab issue list --label "bug,high-priority"

# Filter by assignee
glab issue list --assignee @me
glab issue list --assignee @username

# Filter by milestone
glab issue list --milestone "v1.0"

# Filter by search query
glab issue list --search "scanner timeout"

# Limit results
glab issue list --per-page 50

# Output as JSON (for scripting)
glab issue list --output json
```

### Viewing Issues

```bash
# View issue details
glab issue view <number>

# View with comments
glab issue view <number> --comments

# View in the web browser
glab issue view <number> --web

# Output as JSON
glab issue view <number> --output json
```

### Creating Issues

```bash
# Simple creation
glab issue create --title "Bug: scanner crashes on empty input"

# With description
glab issue create \
    --title "Bug: scanner crashes on empty input" \
    --description "$(cat <<'EOF'
## Description

The scanner panics when given an empty byte slice as input.

## Steps to Reproduce

1. Create a Scanner instance.
2. Call `scan(&[])`.
3. Observe the panic.

## Expected Behavior

Should return an error, not panic.

## Actual Behavior

Panics with "index out of bounds".
EOF
)"

# With labels and assignee
glab issue create \
    --title "Bug: scanner crashes" \
    --label "bug,high-priority" \
    --assignee @me

# With milestone
glab issue create \
    --title "feat: add device enumeration" \
    --milestone "v1.0"

# Confidential issue
glab issue create \
    --title "Security: buffer overflow in parser" \
    --confidential
```

### Updating Issues

```bash
# Update title
glab issue update <number> --title "New title"

# Update description
glab issue update <number> --description "New description"

# Add labels
glab issue update <number> --label "in-progress"

# Remove labels
glab issue update <number> --unlabel "todo"

# Change assignee
glab issue update <number> --assignee @username

# Set milestone
glab issue update <number> --milestone "v1.0"

# Lock discussion
glab issue update <number> --lock-discussion
```

### Closing and Reopening

```bash
# Close an issue
glab issue close <number>

# Reopen an issue
glab issue reopen <number>
```

### Commenting

```bash
# Add a comment
glab issue comment <number> -m "Started working on this."

# Add a multi-line comment
glab issue comment <number> -m "$(cat <<'EOF'
Investigation results:

The crash occurs because the parser does not validate
input length before accessing index 0. Fix will add a
bounds check at the entry point.

Estimated fix time: 1 hour.
EOF
)"
```

### Subscribing

```bash
# Subscribe to notifications
glab issue subscribe <number>

# Unsubscribe
glab issue unsubscribe <number>
```

---

## Merge Request Commands

### Creating Merge Requests

```bash
# Basic creation (uses current branch)
glab mr create --title "feat: add device enumeration"

# With full description
glab mr create \
    --title "feat: add device enumeration" \
    --description "$(cat <<'EOF'
## Summary

Adds USB device enumeration support.

Closes #42

## Changes

- Added Scanner struct for device discovery.
- Added DeviceInfo struct for device metadata.
- Added unit tests for all scanner methods.

## Test Plan

- [x] Unit tests pass
- [x] Integration tests pass
- [ ] Manual testing on target hardware

## Checklist

- [x] Code follows project conventions
- [x] Documentation updated
- [x] Tests added
- [x] No security issues
EOF
)"

# With specific target branch
glab mr create --target-branch develop --title "feat: description"

# As draft
glab mr create --draft --title "feat: work in progress"

# With assignee and reviewer
glab mr create \
    --title "feat: description" \
    --assignee @me \
    --reviewer @reviewer

# With labels
glab mr create --label "feature,review-needed" --title "feat: description"

# With milestone
glab mr create --milestone "v1.0" --title "feat: description"

# Allow collaboration (allow maintainers to push)
glab mr create --allow-collaboration --title "feat: description"

# Auto-merge when pipeline succeeds
glab mr create --auto-merge --title "feat: description"
```

### Viewing Merge Requests

```bash
# View MR details
glab mr view <number>

# View with comments
glab mr view <number> --comments

# View in web browser
glab mr view <number> --web

# View diff statistics
glab mr diff <number>

# View diff with full content
glab mr diff <number> --color always
```

### Listing Merge Requests

```bash
# List open MRs
glab mr list

# List MRs you need to review
glab mr list --reviewer @me

# List your MRs
glab mr list --author @me

# List merged MRs
glab mr list --merged

# List MRs with specific label
glab mr list --label "review-needed"

# Output as JSON
glab mr list --output json
```

### Checking Out MRs

```bash
# Check out an MR branch locally
glab mr checkout <number>

# Check out and create a local branch with a specific name
glab mr checkout <number> --branch local-branch-name
```

### Updating Merge Requests

```bash
# Update title
glab mr update <number> --title "feat: updated title"

# Update description
glab mr update <number> --description "Updated description"

# Add labels
glab mr update <number> --label "approved"

# Remove draft status (mark as ready)
glab mr update <number> --ready

# Set as draft
glab mr update <number> --draft
```

### Approving and Merging

```bash
# Approve an MR
glab mr approve <number>

# Revoke approval
glab mr revoke <number>

# Merge an MR
glab mr merge <number>

# Merge with squash
glab mr merge <number> --squash

# Merge and delete source branch
glab mr merge <number> --remove-source-branch

# Merge with specific commit message
glab mr merge <number> --message "feat: add device enumeration (#42)"

# Merge when pipeline succeeds
glab mr merge <number> --when-pipeline-succeeds
```

### Closing Merge Requests

```bash
# Close without merging
glab mr close <number>

# Reopen a closed MR
glab mr reopen <number>
```

### Adding Comments

```bash
# Add a general comment
glab mr comment <number> -m "LGTM, approved."

# Add a note (alias for comment)
glab mr note <number> -m "Please check the error handling in scanner.rs"
```

---

## Label Management

```bash
# List labels
glab label list

# Create a label
glab label create "in-progress" --color "#0075ca" --description "Work is in progress"

# Delete a label (if supported by your glab version)
# Otherwise, use the web interface
```

---

## Milestone Management

```bash
# List milestones
glab milestone list

# Create a milestone
glab milestone create "v1.0" --description "First stable release" --due-date "2025-12-31"
```

---

## CI/CD

### Pipeline Status

```bash
# View current pipeline status
glab ci status

# View pipeline details
glab ci view

# View a specific pipeline
glab ci view <pipeline-id>

# View pipeline in web browser
glab ci view --web
```

### Pipeline Operations

```bash
# Retry a failed pipeline
glab ci retry <pipeline-id>

# Cancel a running pipeline
glab ci cancel <pipeline-id>

# View pipeline job logs
glab ci trace <job-id>
```

---

## Repository

```bash
# View repository info
glab repo view

# Clone a repository
glab repo clone <project-path>

# Fork a repository
glab repo fork <project-path>

# Open repository in web browser
glab repo view --web
```

---

## Tips for Effective Issues

### Good Issue Titles

| Good                                          | Bad                   |
|-----------------------------------------------|-----------------------|
| `Bug: scanner panics on empty input`          | `Bug`                 |
| `feat: add USB 3.0 superspeed support`        | `New feature`         |
| `docs: add API reference for scanner module`  | `Update docs`         |
| `perf: reduce allocation in hot loop`         | `Make it faster`      |

### Good Issue Descriptions

Include:

- **What** is the problem or feature.
- **Why** it matters.
- **How** to reproduce (for bugs) or acceptance criteria (for features).
- **Context**: related issues, relevant code paths, links to documentation.

### Good MR Descriptions

Include:

- **Summary**: what changed and why.
- **Issue reference**: `Closes #42` or `Related to #42`.
- **Changes**: bullet list of what was done.
- **Test plan**: how the changes were verified.
- **Checklist**: standard quality gates.

---

## Linking Issues and MRs

### Automatic Closing

Use these keywords in MR descriptions to automatically close issues when the MR is merged:

```
Closes #42
Fixes #42
Resolves #42
```

### Related Issues (No Auto-Close)

```
Related to #42
See #42
Part of #42
```

### Cross-Project References

```
Closes group/project#42
Related to group/other-project#15
```
