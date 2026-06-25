# First-run Onboarding Contract

Fovux should prove value within minutes without a network dependency.

## Required flow

- Studio dashboard offers an initialize-demo-workspace action.
- The action starts or verifies the local backend, then calls `demo_init`.
- `demo_init` creates a compact sample dataset, labels, demo run metadata, model placeholder, export artifact, and README locally.
- Doctor/health surfaces cover Python, packages, GPU availability, disk space, write permissions, HTTP health, and Studio credential state.
- The guided workflow points users to the demo dataset and run for offline exploration.
