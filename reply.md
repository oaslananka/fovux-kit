Created root `AGENTS.md` with verified local workflow commands.

**Verification:**
- All commands match `Taskfile.yml` and `required-local-gates.json` verbatim
- Docs-only diff (only `AGENTS.md` added)
- `git diff --check` passes
- Markdown renders correctly (validated with markdown-it-py)
- Prettier formatting applied (`npx prettier@3.8.3 --write AGENTS.md` → `prettier --check` passes)
