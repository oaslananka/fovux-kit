# Fovux Demo Script

Use this as the release video checklist. The goal is a short, honest recording that shows the product working locally from source.

## Setup

- Open the prepared VS Code workspace.
- Confirm `FOVUX_HOME` points at the demo directory.
- Install the local VSIX built from `fovux-studio`.
- Keep a tiny YOLO fixture and at least one checkpoint under `FOVUX_HOME`.

## 90-Second Flow

1. Open the Fovux activity bar.
2. Run `Fovux: Start Local Server`.
3. Open the Dashboard and show existing run status.
4. Open the Training Launcher, select a preset, and show the dry configuration.
5. Open Dataset Inspector and show sample annotations with bbox overlay.
6. Open Export Wizard, choose a checkpoint, and show target-device guidance.
7. Reveal the exported artifact from the Exports view.

## Capture Notes

- Keep the terminal hidden unless a command is the focus.
- Use a clean `FOVUX_HOME` with meaningful run names.
- Avoid showing real tokens, private paths outside the demo workspace, or unpublished registry credentials.
- Record once with the backend already warmed up, then once from a cold VS Code start.

## Screenshot Set

- Fovux activity bar with Runs, Models, and Exports populated.
- Dashboard with at least one selected run.
- Dataset Inspector with bbox overlay visible.
- Training Launcher preset form.
- Export Wizard after a successful ONNX export.

Release-ready Marketplace screenshots are stored in
`fovux-studio/resources/screenshots/`:

- `dashboard.png`
- `dataset-inspector.png`
- `export-wizard.png`
