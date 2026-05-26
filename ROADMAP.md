# Roadmap

This document outlines the planned evolution of Fovux. Themes and dates are
targets, not commitments, and are subject to change based on community feedback
and resource availability.

## 4.2.0 — Q3 2026

**Theme: Multi-GPU and distributed training.**

- Multi-GPU distributed training orchestration via `torchrun`.
- Training scheduler with queue-based run management.
- Enhanced metrics dashboard with GPU utilization overlays.

**DRI:** @oaslananka

## 4.3.0 — Q4 2026

**Theme: Apple Silicon and extended hub integrations.**

- CoreML optimization support for Apple Silicon edge devices.
- Hugging Face Hub integration for model upload and discovery.
- W&B integration for experiment tracking (opt-in only).

**DRI:** @oaslananka

## 5.0.0 — Q1 2027

**Theme: Breaking changes and API stabilization.**

- Public API surface finalized with retired compatibility shims removed.
- HTTP transport v2 with WebSocket support.
- Plugin system for custom tools.
- Multi-language SDK (Python, TypeScript).

**DRI:** @oaslananka

---

All items are subject to reprioritization. To propose a feature, open a
[Discussion](https://github.com/oaslananka/fovux/discussions) thread.
