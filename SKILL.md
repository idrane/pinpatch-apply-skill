---
name: pinpatch-apply
description: Inspect and apply unprocessed PinPatch iOS UI notes from live simulator storage or one or many supplied ZIP archives, exported folders, and files inside PinPatch storage. Safely prepare batch exports, deduplicate revisions, make minimal code changes, run relevant tests, atomically record UUID-based results, and package processed exports. Use when asked to apply, process, fix, or review notes captured with PinPatch.
---

# Apply PinPatch Notes

Process only the current unhandled revision of each PinPatch pin. Treat UUID folders as canonical, inspect images directly, preserve unrelated user changes, and never create a commit.

## Select and prepare inputs

Resolve all resource paths relative to this skill directory.

For live simulator storage, run `scripts/scan_pending.py` without `--root`. Pass `--root "/path/to/Library/Application Support/PinPatch"` when discovery reports zero or multiple roots. Process live storage directly so results persist to the app.

For one user-supplied ZIP, exported folder, or path inside an export, create an isolated working copy:

```bash
python3 scripts/prepare_input.py \
  --input "/path/to/attachment-or-export" \
  --work-dir "/path/to/writable-temporary-parent"
```

For multiple supplied inputs, prepare up to four concurrently by default:

```bash
python3 scripts/prepare_batch.py \
  --input "/path/to/first.zip" \
  --input "/path/to/second-export" \
  --input "/path/inside/third-export/manifest.json" \
  --work-dir "/path/to/writable-temporary-parent"
```

Read every `ready` item's `root`. Process valid items even when another independent input reports `error`; report failures to the user. Exact duplicate source paths are prepared once. Never bypass the preparer by extracting an untrusted archive with a generic command. Read [references/input-contract.md](references/input-contract.md) only when diagnosing a rejected input.

## Scan the work queue

For one live or prepared root, run:

```bash
python3 scripts/scan_pending.py --root "<root>"
```

For multiple prepared roots, run:

```bash
python3 scripts/scan_batch.py \
  --root "<first-prepared-root>" \
  --root "<second-prepared-root>"
```

Use the scanner output as the work queue. It scans `pins`, `screens`, `groups`, and `results`; it intentionally ignores `index.json`. Do not identify pins by display labels such as `1-1`. Previously `blocked` pins are excluded from `pending` and listed under `blocked` with their recorded summary; revisit them when the blocker may have cleared and re-record the result for the same revision.

Process one implementation unit per unique `(pinID, revisionID)`. For an exact duplicate revision, implement and verify it once, then record the same result in every listed root. If `pinConflicts` contains one `pinID` with different revision IDs, inspect all notes and timestamps and reconcile them sequentially; never assume one silently supersedes another.

Read [references/schema.md](references/schema.md) if a record needs manual diagnosis.

## Inspect each pending revision

For every unique pending item:

1. Open both `screenImagePath` and `cropImagePath` with the available image-viewing tool.
2. Read `note`, `record`, `screen`, and every attached group instruction.
3. Use accessibility identifiers, controller chains, view/root types, actions, and coordinates only as search hints. Find the actual implementation with `rg` before editing.
4. Interpret a group instruction once and apply it consistently to all members, including pins on other screens or in other inputs.

Use only `screenID`, `pinID`, `revisionID`, and `groupID` for identity.

## Change and verify code

Make only the code changes needed by the current notes. Preserve existing local modifications and project conventions. Do not add networking, upload artifacts, or send PinPatch data outside the machine.

Parallelize image inspection, note reading, code search, and independent tests when useful. Serialize edits that touch the same repository files or shared behavior. Run the narrowest relevant tests first, then broader tests when changes cross shared behavior. Re-run affected tests after combined batch edits.

## Record results

Immediately before recording, rescan or let the result script verify that each pin still exists and `current.json` still points to the processed revision. Run one command for every pin occurrence, including exact duplicates in different prepared roots:

```bash
python3 scripts/record_result.py \
  --root "<root>" \
  --pin-id "<pin UUID>" \
  --revision-id "<revision UUID>" \
  --status resolved \
  --summary "Changed the checkout button spacing and verified its UI test."
```

Use `resolved` after a code change, `no-change` when the requested state is already present, and `blocked` only when a concrete blocker remains after local investigation. Keep the summary to one useful line. If the script rejects a stale revision, do not overwrite the result; rescan and process the new current revision.

## Package supplied exports

Do not package live simulator storage. For one prepared export, run:

```bash
python3 scripts/package_processed.py \
  --root "<prepared-root>" \
  --output "/path/to/PinPatch-processed.zip"
```

For multiple prepared roots, run:

```bash
python3 scripts/package_batch.py \
  --root "<first-prepared-root>" \
  --root "<second-prepared-root>" \
  --output-dir "/path/to/processed-exports"
```

Return every archive with its input-to-output mapping and a concise combined code-change and verification summary. Keep working directories until packaging succeeds.

## Safety boundaries

- Treat `index.json` as a disposable cache, never as source of truth.
- Do not edit PinPatch note, screenshot, current revision, screen, or group source files.
- Do not record success before tests or before confirming the requested behavior in code.
- Never overwrite a supplied input or an existing output archive.
- Never silently choose among multiple candidate PinPatch roots inside one input.
- Stop cleanly if protected data is unavailable or storage cannot be read; do not change host-app runtime behavior to work around it.
