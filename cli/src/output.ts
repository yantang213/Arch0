import type { Arch0Config, ArchiveResponse, HealthResult } from "./types";
import { redactConfig } from "./config";

export function formatArchiveResponse(response: ArchiveResponse): string {
  const lines = [`Status: ${response.status}`];
  if (response.project_name) {
    lines.push(`Project: ${response.project_name}`);
  }
  if (response.stored_path) {
    lines.push(`Stored: ${response.stored_path}`);
  }
  lines.push(`Confidence: ${response.decision_detail.confidence}`);
  if (response.decision_detail.abstract) {
    lines.push(`Abstract: ${response.decision_detail.abstract}`);
  }
  lines.push(`Reason: ${response.decision_detail.reason}`);
  if (response.warnings.length > 0) {
    lines.push("Warnings:");
    for (const warning of response.warnings) {
      lines.push(`- ${warning}`);
    }
  }
  return lines.join("\n");
}

export function formatConfig(config: Arch0Config): string {
  const redacted = redactConfig(config);
  return [
    `server_url: ${redacted.server_url}`,
    `api_token: ${redacted.api_token}`,
    `send_from_who: ${redacted.send_from_who}`,
    `default_instruction: ${redacted.default_instruction}`
  ].join("\n");
}

export function formatStatus(config: Arch0Config, health: HealthResult, configOk: boolean): string {
  const redacted = redactConfig(config);
  return [
    `Config: ${configOk ? "ok" : "missing"}`,
    `Server URL: ${redacted.server_url}`,
    `API token: ${redacted.api_token}`,
    `Health check: ${health.ok ? "ok" : health.message}`
  ].join("\n");
}

export function formatDoctor(input: {
  configPath: string;
  config: Arch0Config;
  configExists: boolean;
  health: HealthResult;
  tailscale: { found: boolean; status: string };
}): string {
  const redacted = redactConfig(input.config);
  return [
    "Arch0 doctor",
    "",
    `Config file: ${input.configPath}`,
    `Config: ${input.configExists ? "ok" : "missing"}`,
    `Server URL: ${redacted.server_url}`,
    `API token: ${redacted.api_token}`,
    `Health check: ${input.health.ok ? "ok" : input.health.message}`,
    `Tailscale binary: ${input.tailscale.found ? "found" : "missing"}`,
    `Tailscale status: ${input.tailscale.status}`
  ].join("\n");
}

