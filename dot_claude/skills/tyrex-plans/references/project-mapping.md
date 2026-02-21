# Project Mapping

Maps local repository paths to Obsidian vault folders.

## Mapping Table

| Local Path                        | Obsidian Folder      |
|-----------------------------------|----------------------|
| `~/code/tyrex/t-scanner-firmware` | `Tyrex/T-Scanner`    |
| `~/code/tyrex/kub-white-station`  | `Tyrex/White Station` |
| `~/code/tyrex/tyrex-keysas`       | `Tyrex/Keysas`       |
| `~/code/tyrex/tyrex-gate`         | `Tyrex/T-Gate`       |
| `~/code/tyrex/tyrex-ptera-scan`   | `Tyrex/Ptera-Scan`   |

## Fallback Pattern

Any repo under `~/code/tyrex/tyrex-<name>` not explicitly listed above maps to
`Tyrex/Crates/<Name>`, where `<Name>` is derived by:
1. Stripping the `tyrex-` prefix
2. Title-casing the result (e.g., `tyrex-crypto` -> `Tyrex/Crates/Crypto`)

## Resolution Rules

1. Resolve `cwd` to an absolute path.
2. Match against the table using longest-prefix match.
3. If no explicit match, check for the `~/code/tyrex/tyrex-<name>` fallback pattern.
4. If no match at all, ask the user which Obsidian folder to use.

## Obsidian Base Path

All Obsidian folders are relative to: `~/Documents/Perso/Projets/`

Plans are stored in: `~/Documents/Perso/Projets/<Obsidian Folder>/Plans/`

The `Plans/` subdirectory is created automatically if it doesn't exist.

## GitLab Detection

The GitLab project path and hostname are NOT in this table. They are derived
at runtime from the jj/git remote:

```bash
# Get hostname from remote
git remote get-url origin | sed -n 's|.*@\([^:]*\):.*|\1|p'

# Get project path from remote
git remote get-url origin | sed -n 's|.*:\(.*\)\.git|\1|p'
```
