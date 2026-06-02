import { defineConfig } from "tsup";

export default defineConfig([
  {
    entry: { extension: "src/extension.ts" },
    format: ["cjs"],
    platform: "node",
    outDir: "out",
    external: ["vscode"],
    sourcemap: true,
    clean: true,
    dts: false,
  },
  {
    entry: {
      "webviews/dashboard/main": "src/webviews/dashboard/main.tsx",
      "webviews/datasetInspector/main": "src/webviews/datasetInspector/main.tsx",
      "webviews/exportWizard/main": "src/webviews/exportWizard/main.tsx",
      "webviews/compareRuns/main": "src/webviews/compareRuns/main.tsx",
      "webviews/trainingLauncher/main": "src/webviews/trainingLauncher/main.tsx",
      "webviews/timeline/main": "src/webviews/timeline/main.tsx",
      "webviews/annotationEditor/main": "src/webviews/annotationEditor/main.tsx",
    },
    format: ["esm"],
    platform: "browser",
    outDir: "out",
    sourcemap: false,
    clean: false,
    splitting: false,
    minify: true,
    noExternal: ["react", "react-dom"],
    dts: false,
    esbuildOptions(options) {
      options.bundle = true;
      options.packages = "bundle";
    },
    outExtension() {
      return { js: ".js" };
    },
  },
]);
