---
name: init-session
description: >
  Initializes a Claude Code session by reading all configuration files and loading
  pertinent skills based on the project context.
disable-model-invocation: true
---

# Init Session

Session initialization skill for Claude Code. Ensures configuration files are read
and pertinent skills are loaded at the start of a conversation.

## Workflow

### 1. Read Global Configuration

Read `~/.claude/CLAUDE.md` and follow any includes or references it contains.

### 2. Read Project Configuration

In the current working directory, read if they exist:

- `CLAUDE.md` — project-specific instructions
- `AGENTS.md` — agent-specific configuration

For each file, follow any includes or references to other files (e.g., `@file.md` syntax
or explicit "see X file" instructions).

### 3. Detect Project Context

Analyze the project to determine which skills are relevant:

| Indicator                    | Skills to Load                         |
|------------------------------|----------------------------------------|
| `.jj/` or `.git/` directory  | `repo-management` (always load first)  |
| `Cargo.toml`                 | `rust-coding`, `rust-tests`            |
| `go.mod`                     | `go-coding`, `go-tests`                |
| `package.json` + TypeScript  | `ts-coding`, `ts-tests`                |
| `Package.swift`              | `swift-coding`, `swift-tests`          |
| `CMakeLists.txt` / `*.cpp`   | `cpp-coding`, `cpp-tests`              |
| `Dockerfile`                 | `dockerfile-coding`                    |
| `*.sh` scripts               | `bash-coding`                          |
| `.gitlab-ci.yml`             | `gitlab-issues`                        |

### 4. Load Skills

Load skills in this order:

1. **`repo-management`** — always load first if VCS is detected
2. **Language-specific coding skill** — based on project type
3. **Language-specific testing skill** — based on project type
4. **Additional skills** — based on other indicators

### 5. Report Session State

After initialization, provide a brief summary:

```
Session initialized:
- Configuration: [files read]
- VCS: [jj/git/none]
- Project type: [language/framework]
- Skills loaded: [list]
```

## Example Output

```
Session initialized:
- Configuration: ~/.claude/CLAUDE.md, ./CLAUDE.md
- VCS: jj (Jujutsu)
- Project type: Rust binary
- Skills loaded: repo-management, rust-coding, rust-tests
```
