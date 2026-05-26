#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { mkdir } from "node:fs/promises";

function arg(name, fallback = undefined) {
  const index = process.argv.indexOf(name);
  if (index === -1) {
    return fallback;
  }
  return process.argv[index + 1];
}

function packageId(name, version) {
  return `SPDXRef-Package-${`${name}-${version}`.replace(/[^A-Za-z0-9.-]/g, "-")}`;
}

const packagePath = resolve(arg("--package", "package.json"));
const outputPath = resolve(arg("--output", "node-sbom.spdx.json"));
const manifest = JSON.parse(await readFile(packagePath, "utf8"));
const deps = {
  ...manifest.dependencies,
  ...manifest.optionalDependencies,
};

const packages = [
  {
    SPDXID: packageId(manifest.name, manifest.version),
    name: manifest.name,
    versionInfo: manifest.version,
    downloadLocation: "NOASSERTION",
    filesAnalyzed: false,
    licenseConcluded: "NOASSERTION",
    licenseDeclared: manifest.license || "NOASSERTION",
    copyrightText: "NOASSERTION",
  },
  ...Object.entries(deps)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([name, version]) => ({
      SPDXID: packageId(name, version),
      name,
      versionInfo: String(version),
      downloadLocation: "NOASSERTION",
      filesAnalyzed: false,
      licenseConcluded: "NOASSERTION",
      licenseDeclared: "NOASSERTION",
      copyrightText: "NOASSERTION",
    })),
];

const document = {
  spdxVersion: "SPDX-2.3",
  dataLicense: "CC0-1.0",
  SPDXID: "SPDXRef-DOCUMENT",
  name: `${manifest.name}-node-runtime`,
  documentNamespace: `https://github.com/oaslananka/fovux/spdx/${manifest.name}-${manifest.version}`,
  creationInfo: {
    created: new Date(Number(process.env.SOURCE_DATE_EPOCH ?? "0") * 1000)
      .toISOString()
      .replace(/\.\d{3}Z$/, "Z"),
    creators: ["Tool: fovux-build-node-spdx-sbom.mjs"],
  },
  packages,
};

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(document, null, 2)}\n`, "utf8");
