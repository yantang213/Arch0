import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { runSetup, type SetupPrompter } from "../src/commands/setup";
import type { Output } from "../src/types";

function captureOutput(): { output: Output; stdout: string[]; stderr: string[] } {
  const stdout: string[] = [];
  const stderr: string[] = [];
  return {
    stdout,
    stderr,
    output: {
      stdout: (message: string) => stdout.push(message),
      stderr: (message: string) => stderr.push(message)
    }
  };
}

describe("setup command", () => {
  it("keeps the prompter open until remote setup completes", async () => {
    const capture = captureOutput();
    const configDir = await mkdtemp(path.join(tmpdir(), "arch0-setup-test-"));
    const configPath = path.join(configDir, "config.json");
    const answers = [
      "http://server",
      "token",
      "remote-agent:test",
      "Archive completed work."
    ];
    let closed = false;
    const prompter: SetupPrompter = {
      ask: async () => {
        await new Promise((resolve) => setImmediate(resolve));
        if (closed) {
          throw new Error("prompter closed before answer resolved");
        }
        return answers.shift() ?? "";
      },
      close: () => {
        closed = true;
      }
    };
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    const result = await runSetup("remote", { configPath }, {
      output: capture.output,
      prompter,
      fetch: fetchMock as typeof fetch,
      tailscale: async () => ({ found: true, status: "running" })
    });

    expect(result.exitCode).toBe(0);
    expect(closed).toBe(true);
    expect(capture.stdout[0]).toContain("Config saved:");
    expect(capture.stdout[0]).toContain("Health check: ok");
  });
});
