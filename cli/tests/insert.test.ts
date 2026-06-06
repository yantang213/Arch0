import { describe, expect, it, vi } from "vitest";
import { runInsert } from "../src/commands/insert";
import type { ArchiveResponse, Output } from "../src/types";

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

const accepted: ArchiveResponse = {
  status: "accepted",
  project_name: "my-vps-blog",
  decision_detail: { confidence: "high", reason: "ok", abstract: "Documents setup." },
  stored_path: "arch-vault/my-vps-blog/archives/title.md",
  index_updated: true,
  audit_logged: true,
  warnings: []
};

describe("insert command", () => {
  it("dry-run builds payload without sending", async () => {
    const capture = captureOutput();
    const fetchMock = vi.fn();
    const result = await runInsert(
      "work_summary.md",
      { dryRun: true, configPath: "unused" },
      {
        output: capture.output,
        fetch: fetchMock as typeof fetch,
        readConfig: async () => ({ server_url: "http://server", api_token: "secret" }),
        readTextFile: async () => "# Summary\n\nBody",
        system: { username: () => "alice", hostname: () => "host" }
      }
    );
    expect(result.exitCode).toBe(0);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(capture.stdout[0]).toContain('"token": "configured"');
    expect(capture.stdout[0]).not.toContain("secret");
  });

  it("submits and formats accepted response", async () => {
    const capture = captureOutput();
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(accepted), { status: 200 }));
    const result = await runInsert(
      "work_summary.md",
      { configPath: "unused" },
      {
        output: capture.output,
        fetch: fetchMock as typeof fetch,
        readConfig: async () => ({ server_url: "http://server", send_from_who: "remote-agent" }),
        readTextFile: async () => "# Summary\n\nBody",
        system: { username: () => "alice", hostname: () => "host" }
      }
    );
    expect(result.exitCode).toBe(0);
    expect(capture.stdout.join("\n")).toContain("Status: accepted");
    expect(capture.stdout.join("\n")).toContain("Project: my-vps-blog");
  });

  it("returns nonzero when server_url missing", async () => {
    const capture = captureOutput();
    const result = await runInsert("a.md", { configPath: "unused" }, {
      output: capture.output,
      readConfig: async () => ({}),
      readTextFile: async () => "# Summary",
      system: { username: () => "alice", hostname: () => "host" }
    });
    expect(result.exitCode).toBe(1);
    expect(capture.stderr[0]).toContain("server_url is not configured");
  });

  it("returns exit code 3 for rejected response", async () => {
    const capture = captureOutput();
    const rejected: ArchiveResponse = {
      ...accepted,
      status: "rejected",
      project_name: null,
      stored_path: null,
      decision_detail: { confidence: "high", reason: "secret" },
      warnings: ["Detected private key marker."]
    };
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(rejected), { status: 200 }));
    const result = await runInsert("a.md", { configPath: "unused" }, {
      output: capture.output,
      fetch: fetchMock as typeof fetch,
      readConfig: async () => ({ server_url: "http://server" }),
      readTextFile: async () => "# Summary\n\nBody",
      system: { username: () => "alice", hostname: () => "host" }
    });
    expect(result.exitCode).toBe(3);
    expect(capture.stdout.join("\n")).toContain("Status: rejected");
  });
});

