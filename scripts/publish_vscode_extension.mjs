#!/usr/bin/env node
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

const MARKETPLACE_URL = "https://marketplace.visualstudio.com";
const OPEN_VSX_URL = "https://open-vsx.org";
const GALLERY_API_VERSION = "7.2-preview.2";
const MARKETPLACE_ITEM_FLAGS = 914;

function parseArgs(argv) {
  const [channel, ...rest] = argv;
  if (!["marketplace", "open-vsx"].includes(channel)) {
    throw new Error("First argument must be marketplace or open-vsx");
  }
  const options = { channel };
  for (let index = 0; index < rest.length; index += 1) {
    const key = rest[index];
    const value = rest[index + 1];
    if (key === "--vsix" && value) options.vsix = value;
    else if (key === "--publisher" && value) options.publisher = value;
    else if (key === "--name" && value) options.name = value;
    else if (key === "--version" && value) options.version = value;
    else if (key === "--report-path" && value) options.reportPath = value;
    else throw new Error(`Unknown or incomplete argument: ${key}`);
    index += 1;
  }
  for (const key of ["vsix", "publisher", "name", "version"]) {
    if (!options[key]) throw new Error(`--${key} is required`);
  }
  return options;
}

function tokenForChannel(channel) {
  if (channel === "marketplace") {
    return process.env.VSCE_PAT || process.env.VS_MARKETPLACE_TOKEN || "";
  }
  return process.env.OVSX_PAT || process.env.OPEN_VSX_TOKEN || "";
}

function identifier(options) {
  return `${options.publisher}.${options.name}`;
}

async function writeReport(options, state, result, blocker, evidence = []) {
  if (!options.reportPath) return;
  const report = {
    channel:
      options.channel === "marketplace" ? "vscode_marketplace" : "open_vsx",
    state,
    result,
    blocker,
    package: options.name,
    version: options.version,
    identifier: identifier(options),
    run_url: `${process.env.GITHUB_SERVER_URL}/${process.env.GITHUB_REPOSITORY}/actions/runs/${process.env.GITHUB_RUN_ID}`,
    evidence,
  };
  await mkdir(dirname(options.reportPath), { recursive: true });
  await writeFile(options.reportPath, `${JSON.stringify(report, null, 2)}\n`);
}

async function requestJson(url, init = {}) {
  const response = await fetch(url, init);
  const text = await response.text();
  let json;
  try {
    json = text ? JSON.parse(text) : undefined;
  } catch {
    json = undefined;
  }
  if (!response.ok) {
    const truncatedText = text.length > 500 ? `${text.slice(0, 500)}...` : text;
    const message =
      json?.message || json?.error || truncatedText || response.statusText;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return json ?? {};
}

function marketplaceAuthHeader(token) {
  return `Basic ${Buffer.from(`OAuth:${token}`).toString("base64")}`;
}

async function marketplaceExtension(options) {
  const body = {
    filters: [
      {
        criteria: [{ filterType: 7, value: identifier(options) }],
        pageNumber: 1,
        pageSize: 10,
        sortBy: 0,
        sortOrder: 0,
      },
    ],
    assetTypes: [],
    flags: MARKETPLACE_ITEM_FLAGS,
  };
  const json = await requestJson(
    `${MARKETPLACE_URL}/_apis/public/gallery/extensionquery?api-version=7.1-preview.1`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return json.results?.[0]?.extensions?.[0];
}

function marketplaceHasVersion(extension, version) {
  return Boolean(extension?.versions?.some((item) => item.version === version));
}

async function publishMarketplace(options, token) {
  const extension = await marketplaceExtension(options);
  if (marketplaceHasVersion(extension, options.version)) {
    console.log(
      `MARKETPLACE_VERSION_ALREADY_PUBLISHED ${identifier(options)} v${options.version}`,
    );
    await writeReport(options, "already_published", "idempotent_noop", "");
    return;
  }
  const route = extension
    ? `publishers/${encodeURIComponent(options.publisher)}/extensions/${encodeURIComponent(options.name)}`
    : `publishers/${encodeURIComponent(options.publisher)}/extensions`;
  const result = await uploadMarketplaceVsix(
    options,
    token,
    route,
    extension ? "PUT" : "POST",
  );
  if (result === "already_published") {
    console.log(
      `MARKETPLACE_VERSION_ALREADY_PUBLISHED ${identifier(options)} v${options.version}`,
    );
    return;
  }
  console.log(
    `Published ${identifier(options)} v${options.version} to VS Code Marketplace.`,
  );
  await writeReport(options, "published", "fresh_publish_success", "");
}

async function uploadMarketplaceVsix(options, token, route, method) {
  const url = `${MARKETPLACE_URL}/_apis/gallery/${route}?api-version=${GALLERY_API_VERSION}`;
  const response = await fetch(url, {
    method,
    headers: {
      Accept: "application/json",
      Authorization: marketplaceAuthHeader(token),
      "Content-Type": "application/octet-stream",
    },
    body: await readFile(options.vsix),
  });
  const text = await response.text();
  if (response.ok) return "published";
  if (/already.*published|version.*already|already exists/i.test(text)) {
    await writeReport(options, "already_published", "idempotent_noop", "");
    return "already_published";
  }
  let error;
  try {
    error = text ? JSON.parse(text) : {};
  } catch {
    error = { message: text.length > 500 ? `${text.slice(0, 500)}...` : text };
  }
  throw new Error(error.message || error.error || response.statusText);
}

async function openVsxExtension(options) {
  const url = `${OPEN_VSX_URL}/api/${encodeURIComponent(options.publisher)}/${encodeURIComponent(options.name)}`;
  try {
    return await requestJson(url);
  } catch (error) {
    if (error.status === 404) return undefined;
    throw error;
  }
}

function openVsxHasVersion(extension, version) {
  return Boolean(
    extension?.version === version || extension?.allVersions?.[version],
  );
}

async function publishOpenVsx(options, token) {
  const extension = await openVsxExtension(options);
  if (openVsxHasVersion(extension, options.version)) {
    console.log(
      `OPEN_VSX_VERSION_ALREADY_PUBLISHED ${identifier(options)} v${options.version}`,
    );
    await writeReport(options, "already_published", "idempotent_noop", "");
    return;
  }
  const query = new URLSearchParams({ token });
  const response = await fetch(`${OPEN_VSX_URL}/api/-/publish?${query}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: await readFile(options.vsix),
  });
  const text = await response.text();
  if (!response.ok) {
    if (/already.*published|version.*already|already exists/i.test(text)) {
      await writeReport(options, "already_published", "idempotent_noop", "");
      return;
    }
    throw new Error(text || response.statusText);
  }
  const json = text.trim().startsWith("{") ? JSON.parse(text) : {};
  if (json.error) throw new Error(json.error);
  console.log(
    `Published ${identifier(options)} v${options.version} to Open VSX.`,
  );
  if (json.warning) console.log(`Open VSX warning: ${json.warning}`);
  await writeReport(options, "published", "fresh_publish_success", "");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const token = tokenForChannel(options.channel);
  if (!token) {
    const blocker =
      options.channel === "marketplace"
        ? "MARKETPLACE_SECRET_MISSING"
        : "OPEN_VSX_SECRET_MISSING";
    await writeReport(options, "failed", "external_blocker", blocker);
    const error = new Error(blocker);
    error.reportWritten = true;
    throw error;
  }
  try {
    if (options.channel === "marketplace")
      await publishMarketplace(options, token);
    else await publishOpenVsx(options, token);
  } catch (error) {
    if (!error.reportWritten) {
      const blocker =
        options.channel === "marketplace"
          ? "MARKETPLACE_PUBLISH_FAILED"
          : "OPEN_VSX_PUBLISH_FAILED";
      await writeReport(options, "failed", "workflow_failure", blocker);
    }
    throw error;
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
