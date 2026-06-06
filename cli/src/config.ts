import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import type { Arch0Config, ConfigKey } from "./types";

const SUPPORTED_KEYS = new Set<ConfigKey>([
  "server_url",
  "api_token",
  "send_from_who",
  "default_instruction"
]);

export function defaultConfigPath(env: NodeJS.ProcessEnv = process.env): string {
  const base = env.XDG_CONFIG_HOME || path.join(homedir(), ".config");
  return path.join(base, "arch0", "config.json");
}

export async function loadConfig(configPath = defaultConfigPath()): Promise<Arch0Config> {
  try {
    const raw = await readFile(configPath, "utf8");
    return JSON.parse(raw) as Arch0Config;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return {};
    }
    throw error;
  }
}

export async function saveConfig(config: Arch0Config, configPath = defaultConfigPath()): Promise<void> {
  const normalized = normalizeConfig(config);
  await mkdir(path.dirname(configPath), { recursive: true, mode: 0o700 });
  await writeFile(configPath, JSON.stringify(normalized, null, 2) + "\n", { mode: 0o600 });
  await bestEffortChmod(path.dirname(configPath), 0o700);
  await bestEffortChmod(configPath, 0o600);
}

export async function setConfigValue(
  key: string,
  value: string,
  configPath = defaultConfigPath()
): Promise<Arch0Config> {
  if (!SUPPORTED_KEYS.has(key as ConfigKey)) {
    throw new Error(`unsupported config key: ${key}`);
  }
  const config = await loadConfig(configPath);
  const next = normalizeConfig({ ...config, [key]: value });
  await saveConfig(next, configPath);
  return next;
}

export function normalizeConfig(config: Arch0Config): Arch0Config {
  const next: Arch0Config = { ...config };
  if (next.server_url) {
    next.server_url = normalizeServerUrl(next.server_url);
  }
  for (const key of Object.keys(next) as ConfigKey[]) {
    const value = next[key];
    if (typeof value === "string" && value.trim() === "") {
      delete next[key];
    }
  }
  return next;
}

export function normalizeServerUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

export function redactConfig(config: Arch0Config): Record<string, string> {
  return {
    server_url: config.server_url || "(not configured)",
    api_token: config.api_token ? "configured" : "(not configured)",
    send_from_who: config.send_from_who || "(not configured)",
    default_instruction: config.default_instruction || "(not configured)"
  };
}

async function bestEffortChmod(target: string, mode: number): Promise<void> {
  try {
    await chmod(target, mode);
  } catch {
    // Some platforms/filesystems do not support POSIX modes. Config still works.
  }
}

