---
name: gitlab-issues
description: >
  Manage GitLab issues and merge requests using the glab CLI tool. Covers issue triage, branch
  creation from issues, MR creation with templates, code review, and CI/CD pipeline management.
  Use when Claude needs to: (1) create or manage GitLab issues, (2) create merge requests,
  (3) review MRs or check CI status, or (4) any GitLab workflow task using glab.
---

# GitLab Issues Skill

---

## Prerequisites

Before performing any GitLab operations, you MUST:

1. **Read the GitLab workflow reference** at `references/gitlab-workflow.md` in this skill directory.
2. **Verify glab is installed and authenticated:**

```bash
glab auth status
```

3. If glab is not authenticated:

```bash
glab auth login
```

4. **Verify the repository remote** is configured correctly:

```bash
git remote -v
# or
jj git remote list
```

5. **Detect the GitLab hostname and check for SSH resolution issues** — see the
   [Self-Hosted / SSH Hostname](#self-hosted--ssh-hostname-resolution) section below.

---

## Self-Hosted / SSH Hostname Resolution

### The Problem

On self-hosted GitLab instances, SSH config often resolves hostnames to IPs:

```
# ~/.ssh/config
Host tyrex-gl01-dev.kub.local
    Hostname 10.103.4.1
```

When this happens, `glab` sees the resolved IP as the remote host and fails:

```
ERROR: None of the git remotes configured for this repository point to a known
GitLab host. Configured remotes: 10.103.4.1.
```

This affects **all** `glab` commands that auto-detect the repository (`glab mr create`,
`glab issue list`, etc.).

### Detection

Run this check at the start of any GitLab workflow:

```bash
# 1. Get the hostname from git remote
GITLAB_HOST=$(git remote get-url origin | sed -n 's|.*@\([^:]*\):.*|\1|p')

# 2. Check if SSH resolves it to a different hostname/IP
SSH_RESOLVED=$(ssh -G "$GITLAB_HOST" 2>/dev/null | grep '^hostname ' | awk '{print $2}')

# 3. If they differ, glab repo-detection will fail
if [ "$SSH_RESOLVED" != "$GITLAB_HOST" ]; then
    echo "WARNING: SSH resolves $GITLAB_HOST to $SSH_RESOLVED"
    echo "glab commands with auto-detection will fail."
    echo "Use the API fallback workflow instead."
fi
```

### Workaround: Direct API Calls

When `glab` cannot auto-detect the repository, use `glab api --hostname <host>` with
the GitLab REST API directly. See `references/api-fallback.md` for the complete
reference of API-based operations.

**Key patterns:**

```bash
# Get project ID (needed for all API calls)
PROJECT_PATH="group%2Fsubgroup%2Fproject"  # URL-encoded with %2F
glab api --hostname "$GITLAB_HOST" "projects/$PROJECT_PATH" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])"

# Get current user ID (NEVER hardcode — IDs differ per instance)
glab api --hostname "$GITLAB_HOST" 'user' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])"
```

---

## Starting Work on an Issue

### Step 1: View the Issue

```bash
glab issue view <number>
glab issue view <number> --comments
```

### Step 2: Create a Working Branch

With jj:

```bash
jj new -m 'feat: short description (#<number>)'
jj new
```

With git:

```bash
git checkout -b feat/issue-<number>-short-description
```

### Step 3: Reference the Issue

- In commit messages: `feat: add device scanner (#42)`
- In MR descriptions: `Closes #42`

---

## Creating a Merge Request

### Step 1: Push the Branch

With jj:

```bash
jj git push --bookmark <bookmark-name> --allow-new
```

With git:

```bash
git push -u origin <branch-name>
```

### Step 2: Create the MR

**Preferred method** (when `glab` auto-detection works):

```bash
glab mr create \
    --title "feat: short description" \
    --target-branch develop \
    --milestone "Milestone Name" \
    --label "Label1,Label2" \
    --assignee @me \
    --remove-source-branch \
    --squash-before-merge \
    --yes \
    --description "$(cat <<'EOF'
## Summary

Brief description of changes.

Closes #<issue-number>

## Changes

- Change 1
- Change 2

## Test Plan

- [x] Tests pass
- [x] Lints pass
EOF
)"
```

**API fallback** (when auto-detection fails — see `references/api-fallback.md`):

```bash
# 1. Resolve project ID and user ID first
PROJECT_ID=$(glab api --hostname "$GITLAB_HOST" "projects/$PROJECT_PATH" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
USER_ID=$(glab api --hostname "$GITLAB_HOST" 'user' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. Create MR via API
glab api --hostname "$GITLAB_HOST" --method POST "projects/$PROJECT_ID/merge_requests" \
  -f source_branch=<branch> \
  -f target_branch=develop \
  -f title="feat: description" \
  -f assignee_ids="$USER_ID" \
  -f remove_source_branch=true \
  -f squash=true \
  -f description="..." \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['web_url'])"
```

### Milestones

Milestones may be inherited from parent groups. When searching:

```bash
# Include ancestor group milestones
glab api --hostname "$HOST" \
  "projects/$PROJECT_ID/milestones?state=active&per_page=100&include_ancestors=true"
```

When using the API to create MRs, use the milestone's numeric `id` (not `iid`):

```bash
-f milestone_id=91
```

### Labels

Label names must match exactly, including separators. Common formats:

- `Feature::Study`, `Maintenance::Refactor`, `Team::R&D` (with `::`)
- `bug`, `high-priority` (simple names)

List available labels (including from ancestor groups):

```bash
glab api --hostname "$HOST" \
  "projects/$PROJECT_ID/labels?per_page=100&include_ancestor_groups=true"
```

---

## MR Description Template

```markdown
## Summary

Brief description of WHAT was changed and WHY.

Closes #<issue-number>

## Changes

- Change 1: what was done and why.
- Change 2: what was done and why.

## Test Plan

- [ ] Unit tests pass
- [ ] Lints pass
- [ ] Manual testing done for [specific scenario]
```

---

## Additional Operations

See `references/gitlab-workflow.md` for the complete glab command reference (issues,
MRs, CI/CD, labels, milestones).

See `references/api-fallback.md` for direct API patterns when `glab` auto-detection fails.

---

## Agent Workflow Instructions

When asked to create a merge request, follow these steps:

### 1. Check Authentication and Repository Detection

```bash
glab auth status
```

Identify the GitLab hostname from the git remote. Check if SSH resolves it
differently. If it does, use the API fallback workflow from `references/api-fallback.md`.

### 2. Gather Context

- Review all changes in the branch (diff, commit log).
- Check available milestones and labels if the user specified them.

### 3. Resolve User Identity

**NEVER hardcode user IDs.** Always resolve dynamically:

```bash
glab api --hostname "$HOST" 'user'
```

### 4. Create the MR

- Use `glab mr create` if auto-detection works.
- Fall back to `glab api --method POST` if it doesn't.
- Always verify the MR URL in the response.
- Always verify the assignee is correct (check the response).

### 5. Report Back

Return the MR URL to the user.
