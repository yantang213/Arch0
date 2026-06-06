import { execFile } from "node:child_process";
import { promisify } from "node:util";
import os from "node:os";
import path from "node:path";
import { access } from "node:fs/promises";
import { constants } from "node:fs";
import type { SystemInfo } from "./types";

const execFileAsync = promisify(execFile);

export const nodeSystemInfo: SystemInfo = {
  username: () => os.userInfo().username || "unknown",
  hostname: () => os.hostname() || "unknown"
};

export async function findExecutable(command: string, envPath = process.env.PATH || ""): Promise<string | null> {
  for (const dir of envPath.split(path.delimiter)) {
    if (!dir) continue;
    const candidate = path.join(dir, command);
    try {
      await access(candidate, constants.X_OK);
      return candidate;
    } catch {
      // Keep scanning.
    }
  }
  return null;
}

export async function tailscaleDiagnostics(): Promise<{ found: boolean; status: string }> {
  const executable = await findExecutable("tailscale");
  if (!executable) {
    return { found: false, status: "not installed" };
  }
  try {
    const { stdout } = await execFileAsync(executable, ["status", "--peers=false"], { timeout: 5000 });
    const firstLine = stdout.split(/\r?\n/).find(Boolean);
    return { found: true, status: firstLine ? `running (${firstLine})` : "running" };
  } catch (error) {
    return { found: true, status: `found but status failed: ${(error as Error).message}` };
  }
}

