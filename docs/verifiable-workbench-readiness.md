# Verifiable Workbench Readiness

This document closes the roadmap epic for making Fovux a verifiable, safe, local-first computer-vision workbench.

## Readiness pillars

- Release/version identity and public registry verification are covered by docs truth, release process, supply-chain verification, and Studio release evidence gates.
- Risky actions are controlled by challenge flow, agent policy, HTTP auth/origin policy, audit schema, and path validation gates.
- Training/export workflows are covered by train preflight, guided workflow, dashboard resilience, benchmark reproducibility, INT8 calibration, export matrix, and deployment profile gates.
- Dataset and annotation workflows are covered by dataset intelligence and review queue gates.
- Studio guided UX is covered by first-run onboarding, Studio smoke checks, dashboard resilience, and release evidence gates.
- Governance and extensibility are covered by API stability, ADRs, contributor ladder, issue lifecycle, MCP threat model, and MCP Apps strategy decisions.

## Closure rule

The roadmap is complete when every corresponding quality gate exists, passes locally, and all child issues are closed or superseded by documented ADR decisions.
