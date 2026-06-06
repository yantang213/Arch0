import type { CommandResult, Output } from "../types";
import { loadConfig, saveConfig, setConfigValue } from "../config";
import { formatConfig } from "../output";

export async function runConfigShow(
  options: { configPath?: string },
  deps: { output: Output; readConfig?: typeof loadConfig }
): Promise<CommandResult> {
  const config = await (deps.readConfig ?? loadConfig)(options.configPath);
  deps.output.stdout(formatConfig(config));
  return { exitCode: 0 };
}

export async function runConfigSet(
  key: string,
  value: string,
  options: { configPath?: string },
  deps: { output: Output; setValue?: typeof setConfigValue }
): Promise<CommandResult> {
  try {
    const config = await (deps.setValue ?? setConfigValue)(key, value, options.configPath);
    deps.output.stdout(formatConfig(config));
    return { exitCode: 0 };
  } catch (error) {
    deps.output.stderr(`Error: ${(error as Error).message}`);
    return { exitCode: 1 };
  }
}

export async function saveSetupConfig(config: Record<string, string | undefined>, configPath?: string): Promise<void> {
  await saveConfig(config, configPath);
}

