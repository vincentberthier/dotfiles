# Metadata

- Type: epic
- Epic: &NNN
- Project: <gitlab-project-path>
- Milestone: <milestone-name>

---

# Context

<!-- Why this work is needed. Answer ALL of:
     - What problem does this solve?
     - What prompted it? (customer feedback, study, tech debt)
     - What constraints exist? (hardware, backward compat, timeline)
     - Links to relevant studies, RFCs, prior art. -->

# Technical Decisions (Cross-Phase)

<!-- Decisions affecting multiple phases. Agree on these BEFORE implementation.
     Delete this section if there are no cross-phase decisions. -->

### D1. Title

**Decision:** <chosen approach>

**Alternatives considered:** <what else was evaluated>

**Rationale:** <why this approach wins>

<!-- Add code sketches for API designs that downstream phases depend on. -->

# Plan

## Phase 1: Title

**Goal:** <one sentence — what is true after this phase that wasn't before>

**GitLab scope:** <what the issue covers — specific enough to prevent scope creep>

- Weight: N
- Labels: Label1, Label2

### Substeps

<!-- Each substep must be specific enough to implement without guessing.
     Include code sketches for non-obvious APIs.
     Reference existing code to modify (file:line when possible). -->

#### 1.1 Title

#### 1.2 Title

### Files Modified

| File   | Action | Notes |
|--------|--------|-------|

### Testing

<!-- Not "it works" but HOW to verify.
     Include: commands to run, expected output, manual test steps. -->

- [ ] Criterion 1
- [ ] Criterion 2

### Risks

<!-- What could go wrong and how to mitigate.
     Consider: memory budget, performance, backward compat, blocking deps. -->

- Risk 1 -> mitigation

## Phase 2: Title

<!-- Same structure as Phase 1. Repeat for all phases. -->

# Final Audit

<!-- Criteria to verify after ALL phases are complete.
     Fill in project-specific details for each line. -->

- Architecture review: <what to check>
- Code quality: `just checks` <plus any project-specific commands>
- Test coverage: <coverage targets for new code>
- Security review: <relevant audit skills to load>
- Performance: <benchmarks, memory budget>
- Dead code: <verify no remnants of removed modules>
- Documentation: <what docs to update>

# Open Questions

<!-- Unresolved items to investigate during implementation. Delete if none. -->
