import { describe, expect, it } from "vitest";
import { runConfigSet, runConfigShow } from "../src/commands/config";
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

describe("config command", () => {
  it("shows redacted config", async () => {
    const capture = captureOutput();
    const result = await runConfigShow({ configPath: "unused" }, {
      output: capture.output,
      readConfig: async () => ({ server_url: "http://server", api_token: "secret" })
    });
    expect(result.exitCode).toBe(0);
    expect(capture.stdout[0]).toContain("api_token: configured");
    expect(capture.stdout[0]).not.toContain("secret");
  });

  it("reports unsupported set key", async () => {
    const capture = captureOutput();
    const result = await runConfigSet("bad_key", "value", { configPath: "unused" }, {
      output: capture.output,
      setValue: async () => {
        throw new Error("unsupported config key: bad_key");
      }
    });
    expect(result.exitCode).toBe(1);
    expect(capture.stderr[0]).toContain("unsupported config key");
  });
});

