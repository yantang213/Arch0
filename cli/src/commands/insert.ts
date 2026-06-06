import { readFile } from "node:fs/promises";
import type { Arch0Config, CommandResult, Output, SystemInfo } from "../types";
import { loadConfig } from "../config";
import { Arch0HttpError, insertArchive, type FetchLike } from "../http";
import { formatArchiveResponse } from "../output";
import { buildInsertPayload } from "../payload";
import { nodeSystemInfo } from "../system";

export type InsertOptions = {
  title?: string;
  from?: string;
  instruction?: string;
  serverUrl?: string;
  token?: string;
  dryRun?: boolean;
  json?: boolean;
  configPath?: string;
};

export async function runInsert(
  markdownFile: string,
  options: InsertOptions,
  deps: {
    output: Output;
    fetch?: FetchLike;
    system?: SystemInfo;
    readConfig?: (configPath?: string) => Promise<Arch0Config>;
    readTextFile?: (filePath: string) => Promise<string>;
  }
): Promise<CommandResult> {
  const readConfig = deps.readConfig ?? loadConfig;
  const readTextFile = deps.readTextFile ?? ((filePath: string) => readFile(filePath, "utf8"));
  const config = await readConfig(options.configPath);
  const serverUrl = (options.serverUrl || config.server_url)?.replace(/\/+$/, "");
  if (!serverUrl) {
    deps.output.stderr("Error: server_url is not configured.\nRun: arch0 setup remote");
    return { exitCode: 1 };
  }

  const archiveContent = await readTextFile(markdownFile);
  const payload = buildInsertPayload({
    filePath: markdownFile,
    fileContent: archiveContent,
    title: options.title,
    from: options.from,
    instruction: options.instruction,
    config,
    system: deps.system ?? nodeSystemInfo
  });
  const token = options.token || config.api_token;

  if (options.dryRun) {
    const dryRunPayload = {
      target_url: `${serverUrl}/v0.1/archives`,
      token: token ? "configured" : "(not configured)",
      payload: { ...payload, archive_content: `[${archiveContent.length} chars]` }
    };
    deps.output.stdout(JSON.stringify(dryRunPayload, null, 2));
    return { exitCode: 0 };
  }

  try {
    const response = await insertArchive(serverUrl, payload, token, deps.fetch);
    deps.output.stdout(options.json ? JSON.stringify(response, null, 2) : formatArchiveResponse(response));
    return { exitCode: response.status === "rejected" ? 3 : 0 };
  } catch (error) {
    if (error instanceof Arch0HttpError) {
      deps.output.stderr(`Error: ${error.message}`);
      return { exitCode: error.exitCode };
    }
    throw error;
  }
}

