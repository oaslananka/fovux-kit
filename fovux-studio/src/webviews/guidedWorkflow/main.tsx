import * as React from "react";
import { createRoot } from "react-dom/client";
import { GUIDED_WORKFLOW_STAGES } from "../../fovux/guidedWorkflow";

type InitialState = { stages?: typeof GUIDED_WORKFLOW_STAGES };
const state = (window as unknown as { __FOVUX_INITIAL_STATE__?: InitialState })
  .__FOVUX_INITIAL_STATE__;
const stages = state?.stages ?? GUIDED_WORKFLOW_STAGES;

function GuidedWorkflowApp(): React.ReactElement {
  return (
    <main style={{ padding: 24, display: "grid", gap: 16, width: "100%", boxSizing: "border-box" }}>
      <header>
        <h1>Fovux Guided Workflow</h1>
        <p>Dataset discovery to deployment advice.</p>
      </header>
      <section style={{ display: "grid", gap: 12 }}>
        {stages.map((stage, index) => (
          <article
            key={stage.id}
            style={{
              border: "1px solid var(--vscode-panel-border)",
              borderRadius: 12,
              padding: 16,
            }}
          >
            <strong>
              {index + 1}. {stage.title}
            </strong>
            <p>
              Status: <code>{stage.status}</code>
            </p>
            <p>
              MCP tool(s): <code>{stage.mcpToolName}</code>
            </p>
            <p>
              CLI: <code>{stage.cliCommand}</code>
            </p>
            <p>
              Inputs: <code>{JSON.stringify(stage.requiredInputs)}</code>
            </p>
            <p>Next: {stage.nextActions.join(" - ")}</p>
            <p>Fix steps: {stage.remediation.join(" - ")}</p>
            <p>Offline: {stage.offlineDemo}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(<GuidedWorkflowApp />);
