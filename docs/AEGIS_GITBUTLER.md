# AEGIS GitButler — GitHub for All Agents (P6.6)

## Install status: DONE (per-user, no sudo)
- Method: official standalone CLI installer (`https://gitbutler.com/install.sh`),
  inspected before running (bootstrap only fetches from `app.gitbutler.com` /
  `releases.gitbutler.com`, signature-verified). No root used.
- Binary: `/home/adarshjii/.local/bin/but`
- Version: `but 0.22.3` (Release channel, verified via `but --version`)
- Updater: `but update install` / `but update --help`
- Rejected alternatives: AUR `gitbutler`/`gitbutler-bin` (needs sudo via
  pacman -U + heavy GUI deps gtk3/webkit2gtk; `gitbutler` source package has a
  history of checksum failures); AppImage (upstream marks it experimental with
  poor Arch compat — libpcre2/libcurl mismatch). GUI `deb`/`rpm` not applicable
  on Arch.
- Site research: `gitbutler.com/download` fetch timed out once; install facts
  confirmed via `blog.gitbutler.com/but-for-linux` (2026-03-20) + release
  metadata + AUR pages.

## OAuth / forge auth status: PENDING-USER (not done by agent)
Per task rules, no authentication was performed. `but` talks to GitHub via
`but config forge auth` and `but pr` (create/manage PRs). Nothing is wired yet.

## Remaining user step (exact, one step)
1. In a terminal as yourself (interactive — do not delegate to an agent):
   `but config forge auth` → complete GitHub OAuth in the browser, then verify
   with `but config forge` and `but pr --help`. Until this is done, agents must
   stage commits locally with `but commit` and STOP before `but push`/`but pr`.

## CLI capabilities verified (`but --help`, v0.22.3)
- Queue/commit without raw git: `but status`, `but commit -m`, `but branch`,
  `but squash/move/absorb/reword/uncommit/amend`, `but oplog/undo/redo`.
- Push/remote (gated): `but push [--dry-run] [-f]`, `but pull`, `but land`,
  `but pr new` (needs forge auth). Dry-run first: `but push --dry-run`.
- Project onboarding: `but setup` per repo; `but teardown` to exit GB mode.
- Machine-readable: global `--json` flag for agent tooling.

## Workspace rules — all agents route through GitButler, never raw git push
1. NEVER run raw `git push` / `git commit` for Aegis work. Use `but commit`,
   `but branch`, `but status`. (`git blame/log` read-only inspection is fine;
   GitButler is fully Git-compatible.)
2. One repo = `but setup` once (already Git repos just adopt it). Check
   `but status` before and after every change set.
3. Branch naming: `aegis/<task-id>-<short-slug>` (e.g.
   `aegis/p6-6-gitbutler-docs`). Stacked work: `but branch new` above/below;
   never force-push history others depend on.
4. Commits: small, one logical change each, `but commit -m "<type>: <what>"`.
   Use `--dry-run` thinking: review with `but status` + `but diff` pre-commit.
5. Approval before push: `but push` and `but pr new` REQUIRE explicit human
   approval each time. Default agent flow stops at local `but commit`; report
   branch + commit IDs and ask. No `--with-force` without written approval.
6. Never touch git auth config, never print/paste tokens or secrets, never
   `sudo`, never commit on behalf of auth you don't have. If forge auth is
   missing, record `OAuth PENDING-USER` and stop at local commits.
7. Undo safely: prefer `but undo` over `git reset --hard`; discard only with
   `but discard` after confirmation.
