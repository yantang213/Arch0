import { describe, expect, it, vi } from "vitest";
import { runStatus } from "../src/commands/status";
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

describe("status command", () => {
  it("reports missing server_url", async () => {
    const capture = captureOutput();
    const result = await runStatus({ configPath: "unused" }, {
      output: capture.output,
      readConfig: async () => ({}),
      fileExists: async () => false
    });
    expect(result.exitCode).toBe(1);
    expect(capture.stdout[0]).toContain("Config: missing");
    expect(capture.stdout[0]).toContain("server_url missing");
  });

  it("returns zero on healthy server", async () => {
    const capture = captureOutput();
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    const result = await runStatus({ configPath: "unused" }, {
      output: capture.output,
      fetch: fetchMock as typeof fetch,
      readConfig: async () => ({ server_url: "http://server", api_token: "secret" }),
      fileExists: async () => true
    });
    expect(result.exitCode).toBe(0);
    expect(capture.stdout[0]).toContain("Health check: ok");
    expect(capture.stdout[0]).toContain("API token: configured");
    expect(capture.stdout[0]).not.toContain("secret");
  });
});

