import type { RunSummary } from "./api";

export interface DashboardInitialState {
  baseUrl: string;
  authToken: string | null;
  pollIntervalMs: number;
  initialRuns: RunSummary[];
  initialError: string | null;
  isServerReachable: boolean;
}

export interface DatasetSample {
  path: string;
  uri: string;
  boxes: DatasetSampleBox[];
}

export interface DatasetSampleBox {
  classId: number;
  className: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DatasetInspectorInitialState {
  baseUrl: string;
  authToken: string | null;
  datasetPath: string;
  initialResult: Record<string, unknown> | null;
  samplePreviews: DatasetSample[];
  initialError: string | null;
}

export interface ExportWizardModelArtifact {
  name: string;
  path: string;
  format: string;
  source: string;
}

export interface ExportWizardInitialState {
  baseUrl: string;
  authToken: string | null;
  initialModels: ExportWizardModelArtifact[];
  fovuxHome: string;
  initialError: string | null;
  isServerReachable: boolean;
}

export interface FovuxProfile {
  name: string;
  home: string;
}

export interface CompareRunsInitialState {
  baseUrl: string;
  authToken: string | null;
  initialRuns: RunSummary[];
  initialError: string | null;
  isServerReachable: boolean;
}

export interface TimelineInitialState {
  baseUrl: string;
  authToken: string | null;
  initialRuns: RunSummary[];
  initialError: string | null;
  isServerReachable: boolean;
}

export interface AnnotationEditorInitialState {
  imagePath: string;
  imageUri: string;
  classNames: string[];
  initialBoxes: DatasetSampleBox[];
  initialError: string | null;
}

export interface TrainingLauncherInitialState {
  baseUrl: string;
  authToken: string | null;
  initialModels: ExportWizardModelArtifact[];
  fovuxHome: string;
  initialDatasetPath: string;
  initialError: string | null;
  isServerReachable: boolean;
  userPresets: UserPreset[];
}

export interface TrainingConfig {
  name: string;
  datasetPath: string;
  model: string;
  epochs: number;
  batch: number;
  imgsz: number;
  device: string;
  tags: string;
  extraArgs: string;
  force: boolean;
  maxConcurrentRuns: number;
}

export interface UserPreset {
  name: string;
  config: Omit<TrainingConfig, "name" | "datasetPath" | "force">;
  createdAt: string;
}

export type WebviewToExtensionMessage =
  | { type: "openPath"; path: string }
  | { type: "openDashboard" }
  | { type: "startServer" }
  | { type: "refreshAuthToken" }
  | { type: "saveUserPreset"; preset: UserPreset }
  | { type: "deleteUserPreset"; name: string }
  | { type: "exportUserPresets" }
  | { type: "importUserPresets"; presets: UserPreset[] }
  | { type: "selectFovuxProfile"; profile: FovuxProfile }
  | { type: "saveAnnotation"; imagePath: string; boxes: DatasetSampleBox[] };

export type ExtensionToWebviewMessage =
  | { type: "authTokenUpdated"; authToken: string | null }
  | { type: "userPresetsUpdated"; presets: UserPreset[] }
  | { type: "fovuxProfileUpdated"; profile: FovuxProfile };

declare global {
  interface Window {
    __FOVUX_INITIAL_STATE__?: unknown;
    acquireVsCodeApi?: () => {
      postMessage(message: WebviewToExtensionMessage): void;
      setState(state: unknown): void;
      getState(): unknown;
    };
  }
}

export function readInitialState<T>(fallback: T): T {
  const state = window.__FOVUX_INITIAL_STATE__;
  if (state == null) {
    return fallback;
  }
  return state as T;
}

export function postToExtension(message: WebviewToExtensionMessage): void {
  window.acquireVsCodeApi?.().postMessage(message);
}
