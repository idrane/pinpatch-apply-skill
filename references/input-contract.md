# PinPatch export input contract

The preparer recognizes a directory as a PinPatch root when it contains both `pins/` and `screens/`. The remaining canonical layout is validated later by the `pinpatch-apply` scanner:

```text
PinPatch/
├── manifest.json
├── index.json
├── screens/<screenID>.json
├── pins/<pinID>/
│   ├── assets/screen.png
│   ├── assets/crop.png
│   ├── revisions/<revisionID>/pin.json
│   ├── revisions/<revisionID>/note.md
│   └── current.json
├── groups/<groupID>/group.json
├── groups/<groupID>/note.md
└── results/<pinID>.json
```

`manifest.json`, `index.json`, `groups/`, and `results/` may be absent in partial or older exports. Missing pin revision files and malformed UUIDs are reported by the downstream scanner rather than the archive preparer.

The preparer enforces these fixed archive limits:

- At most 20,000 members.
- At most 2 GiB total uncompressed data.
- At most 512 MiB per member.
- At most a 1,000:1 declared expansion ratio per member.

It rejects encrypted members, symbolic links, absolute paths, parent traversal, backslash paths, duplicate normalized paths, and archives containing zero or multiple PinPatch roots. The root search inside an extracted archive descends at most four directory levels below the archive top, so a deeper root is reported as zero roots found.

For a directory or inner-file input, the preparer walks upward first, then searches no more than four directory levels below the supplied directory. It rejects symbolic links before copying and always creates a separate working copy.

## Batch behavior

`prepare_batch.py` accepts repeated `--input` arguments, prepares up to four distinct inputs concurrently by default, and preserves argument order in its JSON output. `--jobs` may reduce or raise concurrency from 1 through 16. An exact duplicate resolved source path is reported as `duplicate` and points to the earlier input index; if that earlier input fails to prepare, the duplicate is reported as `error` as well so no input is silently skipped.

Preparation failures are isolated. The command returns status 2 when any input fails, but retains and reports successfully prepared roots so valid exports can still be processed. Each successful input receives its own temporary session and can be packaged independently.

`scan_batch.py` reports exact repeated `(pinID, revisionID)` pairs under `duplicates`. It reports one `pinID` paired with different current revision IDs under `pinConflicts`; these require sequential human/agent reconciliation because separate exports may represent divergent or differently aged instructions.

`package_batch.py` writes one archive per root as `PinPatch-processed-001.zip`, `PinPatch-processed-002.zip`, and so on. It never overwrites an existing output. A failure for one root does not delete or overwrite another root's completed archive.
