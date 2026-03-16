# GitLab API Fallback Reference

Use these patterns when `glab` cannot auto-detect the repository (typically on
self-hosted instances where SSH resolves the hostname to an IP).

## Table of Contents

- [Setup](#setup)
- [Project Discovery](#project-discovery)
- [User Identity](#user-identity)
- [Merge Requests](#merge-requests)
- [Milestones](#milestones)
- [Labels](#labels)
- [Issues](#issues)
- [CI/CD Pipelines](#cicd-pipelines)

---

## Setup

All commands require `--hostname` to target the correct GitLab instance:

```bash
# Extract hostname from git remote
GITLAB_HOST=$(git remote get-url origin | sed -n 's|.*@\([^:]*\):.*|\1|p')

# URL-encode the project path (replace / with %2F)
PROJECT_PATH="group%2Fsubgroup%2Fproject"
```

---

## Project Discovery

```bash
# Get project metadata (includes numeric ID)
glab api --hostname "$GITLAB_HOST" "projects/$PROJECT_PATH"

# Extract just the project ID
PROJECT_ID=$(glab api --hostname "$GITLAB_HOST" "projects/$PROJECT_PATH" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

---

## User Identity

**CRITICAL: Never hardcode user IDs.** IDs differ between GitLab instances.

```bash
# Get current authenticated user
glab api --hostname "$GITLAB_HOST" 'user'

# Extract user ID
USER_ID=$(glab api --hostname "$GITLAB_HOST" 'user' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Search for a user by username
glab api --hostname "$GITLAB_HOST" "users?username=john.doe"
```

---

## Merge Requests

### Create

```bash
glab api --hostname "$GITLAB_HOST" --method POST "projects/$PROJECT_ID/merge_requests" \
  -f source_branch=feature-branch \
  -f target_branch=develop \
  -f title="feat: description" \
  -f assignee_ids="$USER_ID" \
  -f milestone_id=91 \
  -f labels="Label1,Label2" \
  -f remove_source_branch=true \
  -f squash=true \
  -f description="MR description here"
```

The response includes `web_url` — always extract and return it:

```bash
| python3 -c "import sys,json; print(json.load(sys.stdin)['web_url'])"
```

### View

```bash
glab api --hostname "$GITLAB_HOST" "projects/$PROJECT_ID/merge_requests/$MR_IID"
```

### List

```bash
# Open MRs
glab api --hostname "$GITLAB_HOST" \
  "projects/$PROJECT_ID/merge_requests?state=opened&per_page=20"

# MRs by author
glab api --hostname "$GITLAB_HOST" \
  "projects/$PROJECT_ID/merge_requests?author_id=$USER_ID&state=opened"
```

### Update

```bash
glab api --hostname "$GITLAB_HOST" --method PUT \
  "projects/$PROJECT_ID/merge_requests/$MR_IID" \
  -f title="updated title" \
  -f assignee_ids="$USER_ID"
```

### Merge

```bash
glab api --hostname "$GITLAB_HOST" --method PUT \
  "projects/$PROJECT_ID/merge_requests/$MR_IID/merge" \
  -f squash=true \
  -f should_remove_source_branch=true
```

---

## Milestones

Project-level milestones may be empty if they are inherited from parent groups.
Always use `include_ancestors=true`:

```bash
# List active milestones (including inherited from groups)
glab api --hostname "$GITLAB_HOST" \
  "projects/$PROJECT_ID/milestones?state=active&per_page=100&include_ancestors=true"
```

When creating MRs, use the milestone's `id` field (the global ID), not `iid`.

---

## Labels

Labels may also be inherited from parent groups:

```bash
# List all available labels
glab api --hostname "$GITLAB_HOST" \
  "projects/$PROJECT_ID/labels?per_page=100&include_ancestor_groups=true"
```

When setting labels on MRs/issues via the API, use comma-separated label names
in the `labels` field. Names must match exactly (case-sensitive, including `::` separators).

---

## Issues

### Create

```bash
glab api --hostname "$GITLAB_HOST" --method POST "projects/$PROJECT_ID/issues" \
  -f title="Bug: description" \
  -f description="Issue description" \
  -f assignee_ids="$USER_ID" \
  -f labels="Bug::Feature" \
  -f milestone_id=91
```

### View

```bash
glab api --hostname "$GITLAB_HOST" "projects/$PROJECT_ID/issues/$ISSUE_IID"
```

### Comment

```bash
glab api --hostname "$GITLAB_HOST" --method POST \
  "projects/$PROJECT_ID/issues/$ISSUE_IID/notes" \
  -f body="Comment text"
```

### Close

```bash
glab api --hostname "$GITLAB_HOST" --method PUT \
  "projects/$PROJECT_ID/issues/$ISSUE_IID" \
  -f state_event=close
```

---

## CI/CD Pipelines

### List pipelines for a branch

```bash
glab api --hostname "$GITLAB_HOST" \
  "projects/$PROJECT_ID/pipelines?ref=branch-name&per_page=5"
```

### Get pipeline status

```bash
glab api --hostname "$GITLAB_HOST" \
  "projects/$PROJECT_ID/pipelines/$PIPELINE_ID"
```

### List jobs in a pipeline

```bash
glab api --hostname "$GITLAB_HOST" \
  "projects/$PROJECT_ID/pipelines/$PIPELINE_ID/jobs"
```

### Retry a failed pipeline

```bash
glab api --hostname "$GITLAB_HOST" --method POST \
  "projects/$PROJECT_ID/pipelines/$PIPELINE_ID/retry"
```
