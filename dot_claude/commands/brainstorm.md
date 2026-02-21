---
allowed-tools: Write
description: Pre-planning discovery session to specify a need before technical planning
---

# Brainstorm

Discovery and specification workflow. The goal is to turn a vague idea or suspicion into
a clear, written statement of need.

**This is a conversation, not an investigation. Never read files, run commands, or look
at code. Explore through questions only.**

The topic is: $ARGUMENTS

---

## Step 1: Classify the Input

Identify what kind of input you're dealing with:

| Type          | Signals                                              | Focus                            |
|---------------|------------------------------------------------------|----------------------------------|
| PROBLEM       | "there's a bug", "something's wrong", "I noticed X" | Understand scope and impact      |
| FEATURE       | "I want to add", "we should support", "what if we"   | Define the value and scope       |
| ARCHITECTURE  | "should we use X or Y", "how should we structure"    | Trade-offs, constraints, fit     |
| INVESTIGATION | "I'm not sure what's happening with X"               | Gather facts before deciding     |

State the classification to the user with a one-line framing of what you understood.

---

## Step 2: Ask Clarifying Questions

Ask 2–4 targeted questions to eliminate whole branches of uncertainty. Use multiple-choice
where possible. Accept compact replies like `1b 2a` or `defaults`.

Good question types:
- **Scope**: Is this affecting all users or specific cases?
- **Trigger**: What made this surface now?
- **Success**: How do we know when this is solved?
- **Constraints**: What can't we change? What must stay compatible?
- **Priority**: Is this blocking something, or exploratory?

Pick the 2–4 that matter most for the input type. Iterate — ask follow-up rounds if needed.

---

## Step 3: Build the Brainstorm Document

Draft the document iteratively. Share key sections with the user as you fill them in.
Ask for corrections before finalizing.

### Document Structure

```markdown
# <Title>

**Date:** YYYY-MM-DD
**Type:** Problem | Feature | Architecture | Investigation
**Status:** Draft

## Context

What prompted this? What's the background? Keep to 2–4 sentences.

## Problem / Opportunity

One clear statement. For problems: what's broken and what's the impact.
For features: what user or system need does this address.

## Desired Outcome

What does "done" look like? How do we know we've succeeded?
Describe the end state, not the path.

## Constraints

What we cannot change. Compatibility requirements. Scope limits.
What is explicitly out of scope.

## Open Questions

What we don't know yet that would affect the approach. Rank by importance.
- [ ] Question one
- [ ] Question two

## Initial Ideas

Rough directions worth exploring — not commitments. 2–4 at most.
Each idea in one sentence. No implementation details.

## Next Steps

- [ ] Answer open questions (list which ones first)
- [ ] Create implementation plan: /tyrex-plan
```

---

## Step 4: Save the Document

Save to `.claude/brainstorm/` relative to cwd. Create the directory if it doesn't exist
(use `mkdir -p` only — no other shell commands).

Filename: `YYYY-MM-DD-<slug>.md` where `<slug>` is a 3–5 word lowercase-kebab summary.

After saving, tell the user the file path and note:
- If open questions remain, address those first before planning.
- When ready: `/tyrex-plan` can take this brainstorm as input.

---

## Anti-Patterns

- Don't read files, run commands, or look at code. This is a conversation.
- Don't jump to solutions. If you catch yourself writing "we should implement...", stop.
- Don't write a design doc. Be honest about uncertainty — open questions are fine.
- Don't resolve open questions with assumptions. If we don't know, say so.
