# span

A habit tracker for the desktop. Check in on a few habits once a day,
watch the month fill in, and keep everything on your own machine — no account,
no cloud, no telemetry.

<img width="1114" height="753" alt="image" src="https://github.com/user-attachments/assets/e30674a9-94a7-4902-8315-ba36a98195af" />

The app lives in `desktop/` and is built with Tauri 2, React 19, TypeScript,
Rust and SQLite.

## The desktop app

`desktop/` is a native, frameless Windows app. The Rust side is a thin command
layer over SQLite (via `rusqlite`); everything visual is React.

Features:

- **Today** — one tap per habit, a week strip, day notes, momentum and streaks.
- **Month / Year / Life** — heatmaps from a single day out to your whole life in
  weeks, each cell clickable.
- **Preferences** — habit editor with reordering and archiving, six themes
  (including a light "Paper"), reminders, launch at login, import/export.
- **Details** — custom titlebar, system tray with close-to-tray, command palette
  (`Ctrl+K`), keyboard day navigation (`←`, `→`, `T`), automatic backups.

### Run it

Requires Node 20+, Rust (stable, MSVC toolchain on Windows) and WebView2.

```bash
cd desktop
npm install
npm run tauri dev
```

### Build an installer

```bash
cd desktop
npm run tauri build
```

Bundles land in `desktop/src-tauri/target/release/bundle/`. On Windows this is
an NSIS installer that installs per-user and needs no administrator rights.

### Where the data lives

- Windows: `%APPDATA%\span\span-v2.db`
- macOS: `~/Library/Application Support/span/span-v2.db`
- Linux: `$XDG_DATA_HOME/span/span-v2.db` or `~/.local/share/span/span-v2.db`

The database is plain SQLite. On first run the new app offers to import your
history from the original app's `span.db`, which is left untouched. Rotating
JSON backups are written next to the database in `backups/`.

### Test

```bash
cd desktop
npm test                          # frontend helpers (Vitest)
cargo test --manifest-path src-tauri/Cargo.toml   # database + IPC layer
```
