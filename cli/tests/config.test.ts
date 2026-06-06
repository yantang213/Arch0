import { mkdtemp, readFile, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { loadConfig, normalizeServerUrl, redactConfig, saveConfig, setConfigValue } from "../src/config";

async function tempConfigPath(): Promise<string> {
  const dir = await mkdtemp(path.join(os.tmpdir(), "arch0-cli-config-"));
  return path.join(dir, "config.json");
}

describe("config", () => {
  it("saves and loads normalized config", async () => {
    const configPath = await tempConfigPath();
    await saveConfig({ server_url: "http://example.test:8000///", api_token: "secret" }, configPath);
    const loaded = await loadConfig(configPath);
    expect(loaded.server_url).toBe("http://example.test:8000");
    expect(loaded.api_token).toBe("secret");
    expect(await readFile(configPath, "utf8")).toContain("server_url");
  });

  it("sets supported config key and rejects unsupported key", async () => {
    const configPath = await tempConfigPath();
    const config = await setConfigValue("server_url", "http://example.test/", configPath);
    expect(config.server_url).toBe("http://example.test");
    await expect(setConfigValue("bad_key", "value", configPath)).rejects.toThrow("unsupported config key");
  });

  it("redacts token", () => {
    expect(redactConfig({ api_token: "secret" }).api_token).toBe("configured");
    expect(redactConfig({}).api_token).toBe("(not configured)");
  });

  it("normalizes trailing slash", () => {
    expect(normalizeServerUrl(" http://a/b/// ")).toBe("http://a/b");
  });

  it("uses restrictive file permissions where supported", async () => {
    const configPath = await tempConfigPath();
    await saveConfig({ server_url: "http://example.test" }, configPath);
    const mode = (await stat(configPath)).mode & 0o777;
    expect(mode & 0o077).toBe(0);
  });
});

