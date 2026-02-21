---
name: tyrex-plans
description: >-
  Tyrex planning workflow connecting GitLab epics/issues with Obsidian vault plans.
  Four modes triggered by commands: (1) /tyrex-plan to interactively create an epic
  or issue plan (accepts &NNN, #NNN, or no argument for discovery),
  (2) /tyrex-plan:dispatch-epic to create GitLab issues and Obsidian structure from
  an epic plan, (3) /tyrex-plan:implement to load a plan and implement it with
  progress tracking, (4) /tyrex-plan:finalize to run the final audit and create the
  MR for a standalone issue (#NNN) or epic (&NNN).
---

# Tyrex Plans

## Prerequisites

Before any operation:

1. Load the `gitlab-tyrex` skill (auth, hostname, API fallback).
2. Detect the GitLab hostname from the git/jj remote. Use the API fallback pattern
   if SSH resolves the hostname to an IP (see gitlab-tyrex skill).
3. Read `references/project-mapping.md` to resolve the current project's Obsidian folder.

---

## Mode 1: Plan (`/tyrex-plan`)

**Argument:** `&NNN` (epic), `#NNN` (issue), or nothing (discovery).

### Entry Points

| Argument        | Meaning                                                    |
|-----------------|------------------------------------------------------------|
| `&NNN`          | Plan an existing epic fetched from GitLab                  |
| `#NNN`          | Plan an existing issue fetched from GitLab                 |
| _(no argument)_ | Escalate current conversation into a planned issue or epic |

### Discovery Flow (no argument)

When invoked without an argument, the conversation has already surfaced a problem
or feature that needs proper planning. Steps:

1. **Summarize** what was discussed into a clear problem/feature statement.
2. **Ask the user:** issue or epic?
3. **Resolve project:** try cwd via `references/project-mapping.md`. If no match, ask.
4. **Load `gitlab-tyrex` skill** if not already loaded from Prerequisites.
5. **Create on GitLab** via API:
   - Issue: `POST /projects/:id/issues` with title + description from the conversation.
   - Epic: `POST /groups/:gid/epics` with title + description.
5. **Continue** into the normal planning workflow below with the new `#NNN` or `&NNN`.

### Planning Workflow

This mode behaves like plan mode: read-only exploration of the codebase, interactive
iteration with the user, writing only to the plan file. **Do not edit source files.**

1. **Load `gitlab-tyrex` skill.**
2. **Fetch from GitLab:**
   - `&NNN` -> fetch epic from GitLab group epics API.
   - `#NNN` -> fetch issue from current project's issues API.
3. **Resolve project:** Use `references/project-mapping.md` to map cwd to an Obsidian
   folder. Derive `{PLANS_PATH}` = `~/Documents/Perso/Projets/<Obsidian Folder>/Plans/`.
4. **Read template:** Load `references/epic-template.md` or `references/issue-template.md`.
5. **Fill metadata:** Populate the `# Metadata` block with epic/issue number, project
   path, and milestone (from the GitLab response).
6. **Explore the codebase:** Understand the technical context before planning. Read
   relevant source files, architecture docs, existing CLAUDE.md.
7. **Build the plan interactively:** Ask the user questions, iterate on sections.
   For epic plans, design each phase with full substeps, files, testing, risks.
8. **Run the planning checklist** (see below) before considering the plan complete.
9. **Write the plan** to its final location:
   - **Issue plan** → `{PLANS_PATH}/<iid> - <Title>.md`
     Written in final Obsidian form: prepend YAML frontmatter (see "Obsidian
     Frontmatter Reference" below), include `# Notes` section at the bottom.
     This file is ready for `/tyrex-plan:implement` — no dispatch step needed.
   - **Epic plan** → `{PLANS_PATH}/epic-<iid>-<slug>.md`
     Written using the epic template structure with `# Metadata` block. No Obsidian
     frontmatter — that gets added during `/tyrex-plan:dispatch-epic`.
     `<slug>` is a short lowercase-kebab-case summary of the epic title.
10. **STOP.** Do not implement. Do not suggest implementing. The plan is done.
    For epic plans, tell the user to run `/tyrex-plan:dispatch-epic` when ready.

### Epic Planning Checklist

Before the epic plan is complete, verify ALL of:

- [ ] Context explains the problem, motivation, and constraints
- [ ] Every technical decision has alternatives + rationale documented
- [ ] Each phase has a clear, testable goal statement
- [ ] Each phase has weight and labels assigned
- [ ] Substeps are specific enough to implement without guessing
- [ ] Code sketches provided for non-obvious APIs or data structures
- [ ] Files Modified table covers every file touched
- [ ] Testing criteria are specific and verifiable (commands, expected output)
- [ ] Risks identified with concrete mitigation strategies
- [ ] Cross-phase dependencies noted (e.g., "device non-functional from Phase 3 to 5")
- [ ] Final audit criteria defined with project-specific commands
- [ ] No phase exceeds ~20 weight (split if too large)

### Issue Planning Checklist

- [ ] Links to GitLab issue (and parent epic if applicable)
- [ ] Objective is a single testable statement
- [ ] Substeps are ordered and specific enough to implement
- [ ] Files Modified table is complete
- [ ] Testing criteria are verifiable
- [ ] Risks identified

---

## Mode 2: Dispatch Epic (`/tyrex-plan:dispatch-epic`)

**Argument:** Path to the epic plan file (e.g., `{PLANS_PATH}/epic-119-usb-storage.md`).

This mode is **epic-only**. Issue plans are written in final form during Mode 1 and
need no dispatch step.

### Workflow

1. **Read the epic plan file** and parse the `# Metadata` block:
   - `Epic:` -> epic reference (e.g., `&119`)
   - `Project:` -> GitLab project path
   - `Milestone:` -> milestone name
2. **Resolve the Obsidian folder** from `references/project-mapping.md`.
   Derive `{PLANS_PATH}` = `~/Documents/Perso/Projets/<Obsidian Folder>/Plans/`.
3. **Extract phases** by parsing `## Phase N: Title` headings under `# Plan`.
   For each phase, also extract:
   - `Weight:` from the `- Weight: N` line
   - `Labels:` from the `- Labels: ...` line
4. **Load `gitlab-tyrex` skill** and set up API access.
5. **Create GitLab issues** for each phase:
   - Title: `Phase N: <phase-title>`
   - Labels: from the plan
   - Weight: from the plan
   - Milestone: same as the epic (resolve milestone ID via API)
   - Assigned to: current user
   - Link each issue to the epic (via epics API: `POST groups/{gid}/epics/{eid}/issues/{issue_id}`)
6. **Create Obsidian folder:** `{PLANS_PATH}/<epic-iid> - <Epic Title>/`
7. **Write `_overview_.md`:**
   ```yaml
   ---
   catégorie: plan-claude
   création: <today>
   statut: Planifié
   tags: []
   type: epic-overview
   epic: "&NNN"
   projet: <obsidian-folder>
   ---
   ```
   Content sections (copied from the plan):
   - Context
   - Technical Decisions (Cross-Phase)
   - Phase Summary table:
     ```markdown
     | Phase | Issue | Title                       | Weight | Status   |
     |-------|-------|-----------------------------|--------|----------|
     | 1     | #52   | [[52 - BOT protocol]]       | 12     | Planifié |
     | 2     | #53   | [[53 - Virtual FAT32]]      | 20     | Planifié |
     ```
   - Final Audit section
   - Open Questions (if any)
8. **Write one file per phase:** `<issue-iid> - <Phase Title>.md`
   ```yaml
   ---
   catégorie: plan-claude
   création: <today>
   statut: Planifié
   tags: []
   type: issue
   issue: "#NNN"
   epic: "&NNN"
   overview: "[[_overview_]]"
   projet: <obsidian-folder>
   ---
   ```
   Content: the phase's Goal, GitLab scope, Substeps, Files Modified, Testing, Risks.
   Add an empty `# Notes` section at the bottom for implementation tracking.
9. **Print summary table** of created issues with their GitLab URLs.
10. **Delete the raw epic plan file** (its content is now split into the Obsidian
    folder structure).

---

## Mode 3: Implement (`/tyrex-plan:implement`)

**Argument:** Issue number (e.g., `32`).

### Setup

1. **Find the plan file** in `~/Documents/Perso/Projets/Tyrex/*/Plans/`:
   - Direct match: `*/Plans/<N> - *.md`
   - Inside epic folders: `*/Plans/*/<N> - *.md`
2. **Read the plan file.** Parse the YAML frontmatter.
3. **If `overview` field exists** -> also read the overview file for cross-phase
   context (Technical Decisions, etc.).
4. **Detect standalone vs epic** from the `epic` frontmatter field.
5. **Load relevant coding skills** based on the project (check project CLAUDE.md
   or detect from repo language — e.g., `rust-coding` for Rust projects).
6. **Load `repo-management` skill** for jj workflow.
7. **Update plan file:** set `statut` to `En cours` (unconditionally — covers both fresh start and resume).

### Check Progress

8. **Scan the `# Notes` section** for completed substeps.
   Completed substeps are marked: `- [x] Substep N completed`
   If some substeps are already done, resume from the first incomplete one.

### Implementation Loop

9. For each incomplete substep:
    a. **Create a described jj changeset:**
       `jj new -m 'type(scope): substep description (#<issue>)'`
    b. **Create scratch space:** `jj new`
    c. **Implement the substep** following the plan's details.
    d. **Squash into parent:** `jj squash`
    e. **Update the plan file in Obsidian:**
       - Add `- [x] Substep N completed` to `# Notes`
       - Add any implementation notes, surprises, decisions made
    f. Repeat for next substep.

### Completion

10. **Standalone issue:**
    - Ensure the last changeset description includes `(closes #<issue>)`.
    - Update plan file: `statut: Terminé`.
    - Tell the user to run `/tyrex-plan:finalize #<issue>` when ready to push and open the MR.

11. **Part of an epic:**
    - Ensure the last changeset description includes `(closes #<issue>)`.
    - Squash remaining work: `jj squash`
    - Push: `jj git push`
    - Update plan file: `statut: Terminé`.
    - Update `_overview_.md`: change this phase's status to `Terminé` in the
      Phase Summary table.
    - Do NOT create an MR — that's handled by `/tyrex-plan:finalize`.

---

## Mode 4: Finalize (`/tyrex-plan:finalize`)

**Argument:** `&NNN` (epic) or `#NNN` (issue).

Dispatch to the appropriate path based on the argument prefix.

---

### Issue Path (`#NNN`)

1. **Find the plan file:** `~/Documents/Perso/Projets/Tyrex/*/Plans/<iid> - *.md`
2. **Read the plan file.** Verify `statut: Terminé` (all substeps done).
3. **Load `gitlab-tyrex` skill.**
4. **Fetch the issue from GitLab** to get its milestone title (used when creating the MR).

#### Audit

5. **Read the Testing section** of the plan. Execute each criterion listed there.
6. **If audit finds issues:** fix them (new changesets), re-run until clean.

#### MR Creation

7. **Set jj bookmark:** `jj bookmark set feature-<issue>-<slug>`
8. **Push:** `jj git push --bookmark <bookmark> --allow-new`
9. **Create MR** via `gitlab-tyrex` skill:
   - Ask user for target branch
   - Title: conventional commit format referencing the issue
   - Description: `Closes #<issue>` + summary of changes
   - Milestone: same as the issue (fetched in step 3, passed via `--milestone`)
   - Delete source branch on merge: yes (`--remove-source-branch`)
   - Squash: no

---

### Epic Path (`&NNN`)

1. **Find the overview:** `~/Documents/Perso/Projets/Tyrex/*/Plans/<epic-iid> - */_overview_.md`
2. **Read the Phase Summary table.** Verify all phases show `Terminé`.
3. **Load `gitlab-tyrex` skill.**
4. **Verify on GitLab** that all phase issues are closed. Also fetch the epic's milestone
   title via the API (used when creating the MR).

#### Final Audit

5. **Read the Final Audit section** from the overview. Execute each criterion:
   - Load appropriate audit skills (e.g., `rust-audit`, `embedded-firmware-audit`)
   - Architecture review: verify diagrams match implementation
   - Code quality: run `just checks` (project-specific, runs everything)
   - Test coverage: run tests, check coverage on new code
   - Security review: per the audit skill's workflow
   - Performance: run benchmarks if defined in the audit section
   - Dead code: verify no remnants of removed modules
   - Documentation: verify docs are updated
6. **If audit finds issues:** report them, fix them (creating new changesets as
   needed), then re-run audit until clean.

#### MR Creation

7. **Set jj bookmark** for the epic branch.
8. **Push:** `jj git push --bookmark <bookmark> --allow-new`
9. **Create MR** via `gitlab-tyrex` skill:
   - Ask user for target branch (standard flow requires explicit target)
   - Title references the epic
   - Description lists all closed phase issues
   - Milestone: same as the epic (fetched in step 3, passed via `--milestone`)
   - Delete source branch on merge: yes (`--remove-source-branch`)
   - Squash: no
10. **Update `_overview_.md`:** `statut: Terminé`

---

## Obsidian Frontmatter Reference

### For issue plans (standalone or epic phase)

```yaml
---
catégorie: plan-claude
création: YYYY-MM-DD
statut: Planifié|En cours|Terminé|Abandonné
tags: []
type: issue
issue: "#NNN"
epic: "&NNN"              # only if part of an epic
overview: "[[_overview_]]" # only if part of an epic
projet: <obsidian-folder>
---
```

### For epic overviews

```yaml
---
catégorie: plan-claude
création: YYYY-MM-DD
statut: Planifié|En cours|Terminé|Abandonné
tags: []
type: epic-overview
epic: "&NNN"
projet: <obsidian-folder>
---
```
