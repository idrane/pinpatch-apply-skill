# PinPatch storage schema

Treat the UUID folders below as canonical. `index.json` is a disposable UI cache and may be absent, stale, or corrupt.

```text
PinPatch/
├── manifest.json
├── index.json
├── screens/<screenID>.json
├── screens/<screenID>/screen.png
├── pins/<pinID>/
│   ├── assets/crop.png
│   ├── revisions/<revisionID>/pin.json
│   ├── revisions/<revisionID>/note.md
│   └── current.json
├── groups/<groupID>/group.json
├── groups/<groupID>/note.md
└── results/<pinID>.json
```

`current.json` selects the only live revision. A pin is pending when `results/<pinID>.json` is absent, invalid, or its `processedRevisionID` differs from the current `revisionID`.

Identifiers are stable UUIDs:

- `screenID`: persistent screen identity
- `pinID`: persistent pin identity
- `revisionID`: one immutable note revision
- `groupID`: cross-screen common instruction identity

Visible labels such as `1-1` are recalculated presentation values. Never use them in filenames, links, lookups, or results.

Screen fingerprints contain the raw navigation title, normalized title, and algorithm version. The normalized title is the only identity input. The first completed pin on a screen creates the shared full-screen screenshot; it remains while that screen has any pins and is removed with the last pin.

Screens with the same normalized title merge, and all untitled screens merge. Framework, controller hierarchy, accessibility content, SwiftUI root type, and presentation style remain available only in per-pin element hints where applicable; they do not determine Screen IDs.

Write results only through `scripts/record_result.py`. It validates the current revision immediately before an atomic replace and writes:

```json
{
  "pinID": "uuid",
  "processedRevisionID": "uuid",
  "status": "resolved | no-change | blocked",
  "summary": "one line"
}
```
