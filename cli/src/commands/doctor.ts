import { access } from "node:fs/promises";
import type { Arch0Config, CommandResult, Output } from "../types";
import { defaultConfigPath, loadConfig } from "../config";
import { healthCheck, type FetchLike } from "../http";
import { formatDoctor } from "../output";
import { tailscaleDiagnostics } from "../system";

export async function runDoctor(
  options: { configPath?: string },
  deps: {
    output: Output;
    fetch?: FetchLike;
    readConfig?: (configPath?: string) => Promise<Arch0Config>;
    fileExists?: (path: string) => Promise<boolean>;
    tailscale?: () => Promise<{ found: boolean; status: string }>;
  }
): Promise<CommandResult> {
  const configPath = options.configPath || defaultConfigPath();
  const fileExists = deps.fileExists ?? exists;
  const readConfig = deps.readConfig ?? loadConfig;
  const configExists = await fileExists(configPath);
  const config = await readConfig(configPath);
  const health = config.server_url
    ? await healthCheck(config.server_url, config.api_token, deps.fetch)
    : { ok: false, message: "server_url missing" };
  const tailscale = await (deps.tailscale ?? tailscaleDiagnostics)();
  deps.output.stdout(formatDoctor({ configPath, config, configExists, health, tailscale }));
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

