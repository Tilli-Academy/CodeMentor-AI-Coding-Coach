# Vendored Monaco editor

The code editor (Explain / Hints / Learning Mode) uses the [Monaco editor](https://microsoft.github.io/monaco-editor/),
vendored locally so the app stays self-contained and works offline / behind the dev
proxy (no CDN, no browser internet needed).

The actual editor files live in `vs/` and are **git-ignored** (~14 MB). Fetch them
with the commands below — pinned to **0.52.2**, the last release that ships the classic
AMD `min/vs` layout the integration in `js/editor.js` relies on (0.53+ switched to a
chunked build that needs a bundler).

```bash
# from the repo root
cd /tmp
npm pack monaco-editor@0.52.2
tar -xzf monaco-editor-0.52.2.tgz package/min/vs
mkdir -p <repo>/frontend/vendor/monaco
cp -r package/min/vs <repo>/frontend/vendor/monaco/vs
```

After this, `frontend/vendor/monaco/vs/loader.js` should exist and the app will load
Monaco automatically. If `vs/` is missing, the app silently falls back to a plain
`<textarea>` — no error, just no syntax highlighting.
