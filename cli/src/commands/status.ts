import { access } from "node:fs/promises";
import type { Arch0Config, CommandResult, Output } from "../types";
import { defaultConfigPath, loadConfig } from "../config";
import { healthCheck, type FetchLike } from "../http";
import { formatStatus } from "../output";

export async function runStatus(
  options: { configPath?: string },
  deps: {
    output: Output;
    fetch?: FetchLike;
    readConfig?: (configPath?: string) => Promise<Arch0Config>;
    fileExists?: (path: string) => Promise<boolean>;
  }
): Promise<CommandResult> {
  const configPath = options.configPath || defaultConfigPath();
  const fileExists = deps.fileExists ?? exists;
  const readConfig = deps.readConfig ?? loadConfig;
  const configExists = await fileExists(configPath);
  const config = await readConfig(configPath);
  if (!config.server_url) {
    deps.output.stdout(formatStatus(config, { ok: false, message: "server_url missing" }, configExists));
    return { exitCode: 1 };
  }
  const health = await healthCheck(config.server_url, config.api_token, deps.fetch);
  deps.output.stdout(formatStatus(config, health, configExists));
  return { exitCode: health.ok ? 0 : 2 };
}

async function exists(target: string): Promise<boolean> {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

