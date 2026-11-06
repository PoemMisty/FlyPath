# Maintaining the FlyPath fork

This repository is a public fork of `dronnix-io/FlyPath` that adds Qt-based
internationalization on top of upstream releases. Keep the fork's commits small
and make every sync reproducible.

## Remotes and branch model

```text
origin    https://github.com/PoemMisty/FlyPath.git   (fork, writable)
upstream  https://github.com/dronnix-io/FlyPath.git  (read-only source)
main      fork release line
```

- `main` contains upstream releases plus the i18n changes.
- Do not rebase or force-push `main`; published tags and CI artifacts must stay
  valid.
- Sync each upstream release on a branch named `sync/upstream-vX.Y.Z`, run CI,
  then merge it into `main` with `--no-ff`.
- Follow the upstream release tags, not arbitrary commits on `upstream/main`.

The fork keeps the upstream `metadata.txt` version (for example `5.0.0`) and
distinguishes fork releases with git tags such as `v5.0.0-zh.1`.

## One-time setup

The working copy must have full history so old tags and merge bases are
available. A shallow clone cannot reliably compare releases.

```bash
git fetch --unshallow upstream
git fetch --prune --tags upstream
git tag --list | sort -V | tail -20
```

Make sure GitHub CLI authentication works for the fork:

```bash
gh auth status
gh auth setup-git
```

## Sync a new upstream release

```bash
# 1. Fetch the release
git fetch --prune --tags upstream
git tag --list 'v*' | sort -V | tail -5

# 2. Start from the current release line
git switch main
git pull --ff-only origin main
git switch -c sync/upstream-vX.Y.Z

# 3. Merge the upstream tag
git merge --no-ff vX.Y.Z
```

Resolve conflicts with these rules:

- Take upstream behavior and logic first.
- Re-apply `tr()` / `trn()` to new or changed user-facing strings.
- Keep stable data untranslated: drone and camera names, WPML/KMZ format terms,
  URLs, settings keys, and protocol values used by the website contract.
- Do not hand-merge `i18n/*.ts`; regenerate the catalog from the merged code.

## Update the translation catalog

`tools/update_translations.py` keys translations by the exact English source
string. Existing translations are preserved, new sources are written with
`type="unfinished"`, and obsolete sources are removed.

```bash
# Regenerate the catalog after the merge
python tools/update_translations.py --lang zh_CN

# Show what still needs translating
python tools/update_translations.py --list-unfinished

# Translate every unfinished entry in i18n/FlyPath_zh_CN.ts

# Fail on missing/obsolete sources, placeholder mismatches, and untranslated text
python tools/update_translations.py --check --strict
```

When upstream changes an English source string, the old translation is treated
as obsolete. Recover the previous wording from an older tag if useful:

```bash
git show v5.0.0-zh.1:i18n/FlyPath_zh_CN.ts > /tmp/opencode/old_zh_CN.ts
```

Keep placeholders identical between source and translation. For example,
`{area:.1f}` must not become `{area}` or `{面积}`.

## Verify and publish

Run the same checks as CI before pushing:

```bash
python -m py_compile $(git ls-files '*.py')
python -m pyflakes $(git ls-files '*.py')
python tools/update_translations.py --check --strict
python -m pytest -q tests
```

Commit the merge and the catalog refresh separately:

```bash
git add -A
git commit -m "Merge upstream vX.Y.Z"

git add i18n/FlyPath_zh_CN.ts
git commit -m "Refresh zh_CN translations for vX.Y.Z"

git push -u origin sync/upstream-vX.Y.Z
```

Wait for the `CI` workflow to pass, then merge and tag:

```bash
git switch main
git merge --no-ff sync/upstream-vX.Y.Z
git push origin main

git tag -a vX.Y.Z-zh.N -m "FlyPath X.Y.Z with zh_CN translations"
git push origin vX.Y.Z-zh.N
```

The `Release` workflow builds and verifies the plugin ZIP in the official QGIS
Docker image, then attaches `dist/FlyPath-*.zip` to a GitHub Release for the
tag. The same ZIP is also available from the `CI` run's `FlyPath-plugin`
artifact.

## Release numbering

- `metadata.txt` follows the upstream release version.
- Git tags identify fork releases: `v5.0.0-zh.1`, `v5.0.0-zh.2`, then
  `v5.1.0-zh.1` after the next upstream release.
- Increase the trailing `N` for rebuilds of the same upstream version.
- If the fork is ever submitted to the QGIS plugin repository, give it a
  distinct numeric `metadata.txt` version instead of reusing the upstream one.

## Failure recovery

- Catalog out of date: run the update command again; never hand-edit entries
  that the extractor should generate.
- Missing `lrelease`: not fatal. The plugin reads `.ts` directly; CI compiles a
  `.qm` when the tool is present.
- Release workflow failed before creating a release: fix the workflow on `main`,
  then run the `Release` workflow manually with the existing tag as input.
- A tag was pushed by mistake: delete the tag and release before recreating it.
  Do not move a tag after a release asset has been published.
