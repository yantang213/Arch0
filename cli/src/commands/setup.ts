import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as outputStream } from "node:process";
import type { Arch0Config, CommandResult, Output } from "../types";
import { defaultConfigPath, normalizeServerUrl, saveConfig } from "../config";
import { healthCheck, type FetchLike } from "../http";
import { tailscaleDiagnostics } from "../system";

export type SetupPrompter = {
  ask: (question: string, defaultValue?: string) => Promise<string>;
  close: () => void;
};

export function createReadlinePrompter(): SetupPrompter {
  const rl = createInterface({ input, output: outputStream });
  return {
    ask: async (question: string, defaultValue?: string) => {
      const suffix = defaultValue ? ` [${defaultValue}]` : "";
      const answer = await rl.question(`${question}${suffix}: `);
      return answer.trim() || defaultValue || "";
    },
    close: () => rl.close()
  };
}

export async function runSetup(
  mode: "local" | "remote" | undefined,
  options: { configPath?: string },
  deps: {
    output: Output;
    prompter?: SetupPrompter;
    fetch?: FetchLike;
    tailscale?: () => Promise<{ found: boolean; status: string }>;
  }
): Promise<CommandResult> {
  const prompter = deps.prompter ?? createReadlinePrompter();
  try {
    const resolvedMode =
      mode ?? normalizeMode(await prompter.ask("Configure this machine as local or remote?", "remote"));
    if (resolvedMode !== "local" && resolvedMode !== "remote") {
      deps.output.stderr("Error: setup mode must be local or remote");
      return { exitCode: 1 };
    }
    return await (resolvedMode === "local"
      ? runSetupLocal(options, { ...deps, prompter })
      : runSetupRemote(options, { ...deps, prompter }));
  } finally {
    prompter.close();
  }
}

export async function runSetupLocal(
  options: { configPath?: string },
  deps: { output: Output; prompter: SetupPrompter; fetch?: FetchLike }
): Promise<CommandResult> {
  const serverUrl = normalizeServerUrl(
    await deps.prompter.ask("Arch0 server URL to show remote clients", "http://127.0.0.1:8000")
  );
  const tokenAnswer = await deps.prompter.ask("Configure API token? yes/no", "yes");
  const token =
    tokenAnswer.toLowerCase().startsWith("y")
      ? (await deps.prompter.ask("API token (leave blank to generate)", "")).trim() || generateToken()
      : undefined;
  const config: Arch0Config = {
    server_url: serverUrl,
    api_token: token
  };
  await saveConfig(config, options.configPath);
  const health = await healthCheck(serverUrl, token, deps.fetch);
  deps.output.stdout(
    [
      "Arch0 local setup",
      "",
      `Config saved: ${options.configPath || defaultConfigPath()}`,
      `Server URL: ${serverUrl}`,
      `API token: ${token ? "configured" : "(not configured)"}`,
      `Health check: ${health.ok ? "ok" : health.message}`,
      "",
      "For remote machines, run:",
      "  arch0 setup remote"
    ].join("\n")
  );
  return { exitCode: health.ok ? 0 : 2 };
}

export async function runSetupRemote(
  options: { configPath?: string },
  deps: {
    output: Output;
    prompter: SetupPrompter;
    fetch?: FetchLike;
    tailscale?: () => Promise<{ found: boolean; status: string }>;
  }
): Promise<CommandResult> {
  const serverUrl = normalizeServerUrl(await deps.prompter.ask("Arch0 server URL"));
  if (!serverUrl) {
    deps.output.stderr("Error: server URL is required");
    return { exitCode: 1 };
  }
  const apiToken = await deps.prompter.ask("API token (leave blank if not required)", "");
  const sendFromWho = await deps.prompter.ask("Default sender", "");
  const defaultInstruction = await deps.prompter.ask(
    "Default instruction",
    "Archive this completed work summary for future maintenance context."
  );
  const config: Arch0Config = {
    server_url: serverUrl,
    api_token: apiToken || undefined,
    send_from_who: sendFromWho || undefined,
    default_instruction: defaultInstruction || undefined
  };
  await saveConfig(config, options.configPath);
  const health = await healthCheck(serverUrl, config.api_token, deps.fetch);
  const tailscale = await (deps.tailscale ?? tailscaleDiagnostics)();
  deps.output.stdout(
    [
      `Config saved: ${options.configPath || defaultConfigPath()}`,
      `Health check: ${health.ok ? "ok" : health.message}`,
      `Tailscale: ${tailscale.found ? "installed" : "missing"}`,
      tailscale.found ? `Tailscale status: ${tailscale.status}` : "Install or configure Tailscale/SSH tunnel if remote access is needed."
    ].join("\n")
  );
  return { exitCode: health.ok ? 0 : 2 };
}

function normalizeMode(value: string): "local" | "remote" | undefined {
  const lower = value.trim().toLowerCase();
  if (lower.startsWith("l")) return "local";
  if (lower.startsWith("r")) return "remote";
  return undefined;
}

function generateToken(): string {
  return randomBytes(24).toString("base64url");
}
