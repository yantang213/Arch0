import path from "node:path";
import type { Arch0Config, InsertPayload, SystemInfo } from "./types";

export type InsertPayloadInput = {
  filePath: string;
  fileContent: string;
  title?: string;
  from?: string;
  instruction?: string;
  config?: Arch0Config;
  system: SystemInfo;
};

export function buildInsertPayload(input: InsertPayloadInput): InsertPayload {
  const archiveTitle =
    clean(input.title) ||
    firstMarkdownH1(input.fileContent) ||
    path.basename(input.filePath, path.extname(input.filePath));
  const sender =
    clean(input.from) ||
    clean(input.config?.send_from_who) ||
    `cli:${input.system.username()}@${input.system.hostname()}`;
  const instruction = clean(input.instruction) || clean(input.config?.default_instruction);
  const payload: InsertPayload = {
    cmd_type: "insert",
    archive_title: archiveTitle,
    archive_content: input.fileContent,
    send_from_who: sender
  };
  if (instruction) {
    payload.instruction = instruction;
  }
  return payload;
}

export function firstMarkdownH1(markdown: string): string | undefined {
  for (const line of markdown.split(/\r?\n/)) {
    const match = /^#\s+(.+?)\s*$/.exec(line);
    if (match?.[1]) {
      return match[1].trim();
    }
  }
  return undefined;
}

function clean(value?: string): string | undefined {
  const trimmed = value?.trim();
  return trimmed || undefined;
}

