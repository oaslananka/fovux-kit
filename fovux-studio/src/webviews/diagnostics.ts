export interface DashboardWebviewDiagnostics {
  opened: boolean;
  ready: boolean;
  contentSecurityPolicy: string | null;
  bundleUri: string | null;
}

const EMPTY_DIAGNOSTICS: DashboardWebviewDiagnostics = {
  opened: false,
  ready: false,
  contentSecurityPolicy: null,
  bundleUri: null,
};

let dashboardDiagnostics: DashboardWebviewDiagnostics = { ...EMPTY_DIAGNOSTICS };

export function recordDashboardWebviewOpened(
  contentSecurityPolicy: string,
  bundleUri: string
): void {
  dashboardDiagnostics = {
    opened: true,
    ready: false,
    contentSecurityPolicy,
    bundleUri,
  };
}

export function recordDashboardWebviewReady(): void {
  dashboardDiagnostics = {
    ...dashboardDiagnostics,
    ready: dashboardDiagnostics.opened,
  };
}

export function getDashboardWebviewDiagnostics(): DashboardWebviewDiagnostics {
  return { ...dashboardDiagnostics };
}

export function resetDashboardWebviewDiagnostics(): void {
  dashboardDiagnostics = { ...EMPTY_DIAGNOSTICS };
}
