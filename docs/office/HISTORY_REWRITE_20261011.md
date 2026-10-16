# phase/uri-office history rewrite — 2026-10-11

**Owner approval (2026-10-11), relayed by the URI development session:** rewrite `phase/uri-office` to remove
`research/uri_office_spikes/p2_web/node_modules` from all commits, force-push only `phase/uri-office` to `uri-repo`
(`github.com/sche004-cyber/Uri`), and delete the `phase/uri-office` copy on `origin` (`github.com/sche004-cyber/uri-agent`).
No other branch was touched: not canonical `integration/git-sync-20261008`, not `milestone/*`, not
`ccr-cab5ed06-9hwyc4`.

## Why

Commit `2fbbaed0` ("URI Office M1 service core …") added the P2 spike's installed npm packages: 11,477 files,
182 MiB. They had not been ignored. The repository root `.gitignore` is frozen and does not cover that folder.

The coordinator had also reported "nothing is ignored" from a file listing that was itself filtered with
`grep -v node_modules`. That report was wrong, and this record corrects it.

## What was done

- **Rewrite:** `git filter-branch --index-filter 'git rm -r --cached --ignore-unmatch research/uri_office_spikes/p2_web/node_modules' -- ce1a90c046d2e9566a86d8dccf25df0e2bc98c80..phase/uri-office`. Only the four Office commits were rewritten; the base stays canonical `ce1a90c`.
- **Old tip:** `da2a3de3fe4b426ef3b69cf00c41860bc76e8265`.
- **New tip after the rewrite:** `eef690ffbaaa1078e5ccd4f9e8eb6f52ae372ce9`. It was followed by the commit that adds this record.

| Old commit | New commit | Subject |
|---|---|---|
| 2fbbaed0 | 1b463f70 | feat(office): URI Office M1 service core, cell-patch saving and security tests |
| c517eb71 | 42d12293 | feat(office): current-user-only state folder, history and Google link tests |
| 22ebe1ce | 8034afab | docs(office): AC6 covers the current-user-only state folder |
| da2a3de3 | eef690ff | docs(office): record that canonical lives on uri-repo, not origin |

## Checks before the force-push

All four checks returned the expected result.

1. `git log phase/uri-office -- '*node_modules*'` over the whole branch history, canonical ancestry included, returns nothing. `git ls-tree -r` of each rewritten commit has 0 `node_modules` paths.
2. `git diff da2a3de eef690ff -- . ':!research/uri_office_spikes/p2_web/node_modules'` is empty: the tree is identical apart from the removed folder.
3. The parent of the first rewritten commit is `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80`.
4. The new tip's tree is 297.57 MiB, against 297.22 MiB for canonical `ce1a90c`. The 182 MiB is gone.

## Prevention

- Folder-local `.gitignore` files now cover `node_modules/` and `dist/` in `research/uri_office_spikes/p2_web/` and `uri_ui/office_web/`. The root `.gitignore` is unchanged because it is frozen.
- The npm packages are reinstalled from the committed `package-lock.json` with `npm ci`.
