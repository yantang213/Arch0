import { describe, expect, it, vi } from "vitest";
import { runDoctor } from "../src/commands/doctor";
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

describe("doctor command", () => {
  it("reports tailscale missing but keeps diagnostics useful", async () => {
    const capture = captureOutput();
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    const result = await runDoctor({ configPath: "/tmp/arch0-config.json" }, {
      output: capture.output,
      fetch: fetchMock as typeof fetch,
      readConfig: async () => ({ server_url: "http://server" }),
      fileExists: async () => true,
      tailscale: async () => ({ found: false, status: "not installed" })
    });
    expect(result.exitCode).toBe(0);
    expect(capture.stdout[0]).toContain("Arch0 doctor");
    expect(capture.stdout[0]).toContain("Tailscale binary: missing");
  });
});

