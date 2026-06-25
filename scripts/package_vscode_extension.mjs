#!/usr/bin/env node
import { deflateRawSync } from "node:zlib";
import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { basename, dirname, extname, join, relative, resolve } from "node:path";

const DEFAULT_EXTENSION_DIR = "fovux-studio";
const ZIP_UTF8_FLAG = 0x0800;
const ZIP_DEFLATE_METHOD = 8;
const ZIP_VERSION = 20;
const ZIP_UNIX_VERSION = (3 << 8) | ZIP_VERSION;
const CONTENT_TYPES_PATH = "[Content_Types].xml";
const MANIFEST_PATH = "extension.vsixmanifest";
const MANIFEST_CONTENT_TYPE = "text/xml";
const DEFAULT_CONTENT_TYPES = new Map([
  [".js", "application/javascript"],
  [".json", "application/json"],
  [".map", "application/json"],
  [".md", "text/markdown"],
  [".png", "image/png"],
  [".txt", "text/plain"],
  [".vsixmanifest", MANIFEST_CONTENT_TYPE],
]);
const ALWAYS_IGNORED = new Set([".npmrc", ".vscodeignore"]);

function parseArgs(argv) {
  const options = { extensionDir: DEFAULT_EXTENSION_DIR };
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    const value = argv[index + 1];
    if (key === "--extension-dir" && value) options.extensionDir = value;
    else if (key === "--out" && value) options.out = value;
    else if (key === "--max-size-bytes" && value) options.maxSizeBytes = Number(value);
    else throw new Error(`Unknown or incomplete argument: ${key}`);
    index += 1;
  }
  if (!options.out) throw new Error("--out is required");
  if (options.maxSizeBytes !== undefined && (!Number.isFinite(options.maxSizeBytes) || options.maxSizeBytes <= 0)) {
    throw new Error("--max-size-bytes must be a positive number");
  }
  return options;
}

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

function toPosix(path) {
  return path.replace(/\\/g, "/");
}

function escapeXml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function readIgnorePatterns(extensionDir) {
  try {
    const text = await readFile(join(extensionDir, ".vscodeignore"), "utf8");
    return text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

function matchIgnorePattern(pattern, relPath) {
  if (pattern.endsWith("/**")) {
    const prefix = pattern.slice(0, -3);
    return relPath === prefix || relPath.startsWith(`${prefix}/`);
  }
  if (pattern === "**/*.map") return relPath.endsWith(".map");
  if (pattern === "**/*.ts") return relPath.endsWith(".ts");
  if (pattern === "tmp-runs-*/") return /^tmp-runs-[^/]+\//.test(relPath);
  if (pattern.startsWith("*.")) {
    return !relPath.includes("/") && relPath.endsWith(pattern.slice(1));
  }
  if (!pattern.includes("/")) {
    return relPath === pattern || basename(relPath) === pattern;
  }
  return relPath === pattern;
}

function shouldInclude(relPath, patterns) {
  if (ALWAYS_IGNORED.has(relPath)) return false;
  let included = true;
  for (const rawPattern of patterns) {
    const isNegated = rawPattern.startsWith("!");
    const pattern = isNegated ? rawPattern.slice(1) : rawPattern;
    if (matchIgnorePattern(pattern, relPath)) included = isNegated;
  }
  return included;
}

async function collectLocalFiles(root, current = root) {
  const items = await readdir(current, { withFileTypes: true });
  const files = [];
  for (const item of items) {
    if (item.name === ".git" || item.name === "node_modules") continue;
    const path = join(current, item.name);
    if (item.isDirectory())
      files.push(...(await collectLocalFiles(root, path)));
    else if (item.isFile()) files.push(path);
  }
  return files;
}

function mapVsixPath(relPath) {
  const lower = relPath.toLowerCase();
  if (lower === "readme.md") return "extension/readme.md";
  if (lower === "changelog.md") return "extension/changelog.md";
  if (relPath === "LICENSE") return "extension/LICENSE.txt";
  return `extension/${relPath}`;
}

async function collectPackageFiles(extensionDir) {
  const patterns = await readIgnorePatterns(extensionDir);
  const localFiles = await collectLocalFiles(extensionDir);
  const files = localFiles
    .map((localPath) => ({
      localPath,
      relPath: toPosix(relative(extensionDir, localPath)),
    }))
    .filter(({ relPath }) => shouldInclude(relPath, patterns))
    .map(({ localPath, relPath }) => ({
      localPath,
      path: mapVsixPath(relPath),
    }))
    .sort((left, right) => left.path.localeCompare(right.path));
  return files;
}

function githubUrl(manifest) {
  const raw =
    typeof manifest.repository === "string"
      ? manifest.repository
      : manifest.repository?.url;
  if (!raw) return undefined;
  return raw.replace(/^git\+/, "").replace(/\.git$/, "");
}

function buildTags(manifest) {
  const tags = new Set(manifest.keywords ?? []);
  if (manifest.contributes?.keybindings?.length) tags.add("keybindings");
  if (manifest.contributes?.languageModelTools?.length) {
    tags.add("tools");
    tags.add("language-model-tools");
  }
  return [...tags].join(",");
}

function assetEntries(files, manifest) {
  const paths = new Set(files.map((file) => file.path));
  const entries = [
    ["Microsoft.VisualStudio.Code.Manifest", "extension/package.json"],
    ["Microsoft.VisualStudio.Services.Content.Details", "extension/readme.md"],
    [
      "Microsoft.VisualStudio.Services.Content.Changelog",
      "extension/changelog.md",
    ],
    [
      "Microsoft.VisualStudio.Services.Content.License",
      "extension/LICENSE.txt",
    ],
  ];
  if (manifest.icon)
    entries.push([
      "Microsoft.VisualStudio.Services.Icons.Default",
      `extension/${manifest.icon}`,
    ]);
  return entries
    .filter(([, path]) => paths.has(path))
    .map(
      ([type, path]) =>
        `<Asset Type="${type}" Path="${escapeXml(path)}" Addressable="true" />`,
    )
    .join("\n");
}

function buildVsixManifest(manifest, files) {
  const repoUrl = githubUrl(manifest);
  const bugsUrl =
    typeof manifest.bugs === "string" ? manifest.bugs : manifest.bugs?.url;
  const properties = buildProperties(manifest, repoUrl, bugsUrl);
  return `<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="${escapeXml(manifest.name)}" Version="${escapeXml(manifest.version)}" Publisher="${escapeXml(manifest.publisher)}" />
    <DisplayName>${escapeXml(manifest.displayName ?? manifest.name)}</DisplayName>
    <Description xml:space="preserve">${escapeXml(manifest.description)}</Description>
    <Tags>${escapeXml(buildTags(manifest))}</Tags>
    <Categories>${escapeXml((manifest.categories ?? []).join(","))}</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
${properties}
    </Properties>
    <License>extension/LICENSE.txt</License>
    <Icon>${escapeXml(`extension/${manifest.icon}`)}</Icon>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
${assetEntries(files, manifest)}
  </Assets>
</PackageManifest>
`;
}

function buildProperties(manifest, repoUrl, bugsUrl) {
  const properties = [
    ["Microsoft.VisualStudio.Code.Engine", manifest.engines?.vscode],
    [
      "Microsoft.VisualStudio.Code.ExtensionDependencies",
      (manifest.extensionDependencies ?? []).join(","),
    ],
    [
      "Microsoft.VisualStudio.Code.ExtensionPack",
      (manifest.extensionPack ?? []).join(","),
    ],
    [
      "Microsoft.VisualStudio.Code.ExtensionKind",
      (manifest.extensionKind ?? []).join(","),
    ],
    ["Microsoft.VisualStudio.Code.LocalizedLanguages", ""],
    [
      "Microsoft.VisualStudio.Code.EnabledApiProposals",
      (manifest.enabledApiProposals ?? []).join(","),
    ],
    [
      "Microsoft.VisualStudio.Code.ExecutesCode",
      manifest.main ? "true" : "false",
    ],
    ["Microsoft.VisualStudio.Services.Links.Source", repoUrl],
    ["Microsoft.VisualStudio.Services.Links.Getstarted", repoUrl],
    ["Microsoft.VisualStudio.Services.Links.GitHub", repoUrl],
    ["Microsoft.VisualStudio.Services.Links.Support", bugsUrl],
    ["Microsoft.VisualStudio.Services.Links.Learn", manifest.homepage],
    [
      "Microsoft.VisualStudio.Services.Branding.Color",
      manifest.galleryBanner?.color,
    ],
    [
      "Microsoft.VisualStudio.Services.Branding.Theme",
      manifest.galleryBanner?.theme,
    ],
    ["Microsoft.VisualStudio.Services.GitHubFlavoredMarkdown", "true"],
    ["Microsoft.VisualStudio.Services.Content.Pricing", "Free"],
  ];
  return properties
    .filter(([, value]) => value !== undefined)
    .map(
      ([id, value]) =>
        `      <Property Id="${id}" Value="${escapeXml(value)}" />`,
    )
    .join("\n");
}

function buildContentTypes(files) {
  const extensions = new Set([
    extname(MANIFEST_PATH).toLowerCase(),
    ...files.map((file) => extname(file.path).toLowerCase()),
  ]);
  const defaults = [...extensions]
    .filter((extension) => extension)
    .sort()
    .map((extension) => {
      const contentType =
        DEFAULT_CONTENT_TYPES.get(extension) ?? "application/octet-stream";
      return `<Default Extension="${escapeXml(extension.slice(1))}" ContentType="${contentType}"/>`;
    })
    .join("");
  return `<?xml version="1.0" encoding="utf-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">${defaults}</Types>\n`;
}

async function readEntries(extensionDir) {
  const manifest = await readJson(join(extensionDir, "package.json"));
  const files = await collectPackageFiles(extensionDir);
  const entries = [
    {
      path: MANIFEST_PATH,
      data: Buffer.from(buildVsixManifest(manifest, files)),
    },
    { path: CONTENT_TYPES_PATH, data: Buffer.from(buildContentTypes(files)) },
  ];
  for (const file of files) {
    entries.push({ path: file.path, data: await readFile(file.localPath) });
  }
  return { entries, manifest };
}

const CRC_TABLE = new Uint32Array(256);
for (let index = 0; index < CRC_TABLE.length; index += 1) {
  let crc = index;
  for (let bit = 0; bit < 8; bit += 1) {
    crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  CRC_TABLE[index] = crc >>> 0;
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (let index = 0; index < buffer.length; index += 1) {
    crc = (crc >>> 8) ^ CRC_TABLE[(crc ^ buffer[index]) & 0xff];
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function dosTimestamp(date = new Date()) {
  const time =
    (date.getHours() << 11) |
    (date.getMinutes() << 5) |
    (date.getSeconds() >> 1);
  const day = Math.max(date.getFullYear() - 1980, 0);
  return {
    date: (day << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    time,
  };
}

function localHeader(name, data, compressed, crc, timestamp) {
  const header = Buffer.alloc(30);
  header.writeUInt32LE(0x04034b50, 0);
  header.writeUInt16LE(ZIP_VERSION, 4);
  header.writeUInt16LE(ZIP_UTF8_FLAG, 6);
  header.writeUInt16LE(ZIP_DEFLATE_METHOD, 8);
  header.writeUInt16LE(timestamp.time, 10);
  header.writeUInt16LE(timestamp.date, 12);
  header.writeUInt32LE(crc, 14);
  header.writeUInt32LE(compressed.length, 18);
  header.writeUInt32LE(data.length, 22);
  header.writeUInt16LE(name.length, 26);
  return Buffer.concat([header, name]);
}

function centralHeader(name, data, compressed, crc, timestamp, offset) {
  const header = Buffer.alloc(46);
  header.writeUInt32LE(0x02014b50, 0);
  header.writeUInt16LE(ZIP_UNIX_VERSION, 4);
  header.writeUInt16LE(ZIP_VERSION, 6);
  header.writeUInt16LE(ZIP_UTF8_FLAG, 8);
  header.writeUInt16LE(ZIP_DEFLATE_METHOD, 10);
  header.writeUInt16LE(timestamp.time, 12);
  header.writeUInt16LE(timestamp.date, 14);
  header.writeUInt32LE(crc, 16);
  header.writeUInt32LE(compressed.length, 20);
  header.writeUInt32LE(data.length, 24);
  header.writeUInt16LE(name.length, 28);
  header.writeUInt32LE((0o100644 << 16) >>> 0, 38);
  header.writeUInt32LE(offset, 42);
  return Buffer.concat([header, name]);
}

function endRecord(centralSize, centralOffset, count) {
  const record = Buffer.alloc(22);
  record.writeUInt32LE(0x06054b50, 0);
  record.writeUInt16LE(count, 8);
  record.writeUInt16LE(count, 10);
  record.writeUInt32LE(centralSize, 12);
  record.writeUInt32LE(centralOffset, 16);
  return record;
}

function makeZip(entries) {
  const timestamp = dosTimestamp();
  const locals = [];
  const centrals = [];
  let offset = 0;
  for (const entry of entries) {
    const name = Buffer.from(entry.path);
    const compressed = deflateRawSync(entry.data, { level: 9 });
    const crc = crc32(entry.data);
    const local = localHeader(name, entry.data, compressed, crc, timestamp);
    locals.push(local, compressed);
    centrals.push(
      centralHeader(name, entry.data, compressed, crc, timestamp, offset),
    );
    offset += local.length + compressed.length;
  }
  const central = Buffer.concat(centrals);
  return Buffer.concat([
    ...locals,
    central,
    endRecord(central.length, offset, entries.length),
  ]);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const extensionDir = resolve(options.extensionDir);
  const outPath = resolve(options.out);
  const { entries, manifest } = await readEntries(extensionDir);
  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, makeZip(entries));
  const size = (await stat(outPath)).size;
  if (options.maxSizeBytes !== undefined && size > options.maxSizeBytes) {
    throw new Error(
      `VSIX_PACKAGE_TOO_LARGE ${size} bytes exceeds ${options.maxSizeBytes} bytes.`,
    );
  }
  console.log(
    `Packaged ${manifest.publisher}.${manifest.name} v${manifest.version} to ${outPath} (${size} bytes).`,
  );
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
