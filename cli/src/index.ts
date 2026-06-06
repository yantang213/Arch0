#!/usr/bin/env node
import { Command } from "commander";
import { runConfigSet, runConfigShow } from "./commands/config";
import { runDoctor } from "./commands/doctor";
import { runInsert } from "./commands/insert";
import { runSetup } from "./commands/setup";
import { runStatus } from "./commands/status";
import type { Output } from "./types";

const output: Output = {
  stdout: (message: string) => console.log(message),
  stderr: (message: string) => console.error(message)
};

export function buildProgram(): Command {
  const program = new Command();
  program.name("arch0").description("Thin CLI client for Arch0").version("0.16.1");
  program.option("--config <path>", "config file path");

  const setup = program.command("setup").description("configure Arch0 CLI");
  setup
    .argument("[mode]", "local or remote")
    .action(async (mode: string | undefined) => {
      process.exitCode = (await runSetup(parseMode(mode), rootOptions(program), { output })).exitCode;
    });
  setup
    .command("local")
    .description("configure local Arch0 client settings")
    .action(async () => {
      process.exitCode = (await runSetup("local", rootOptions(program), { output })).exitCode;
    });
  setup
    .command("remote")
    .description("configure remote Arch0 client settings")
    .action(async () => {
      process.exitCode = (await runSetup("remote", rootOptions(program), { output })).exitCode;
    });

  program
    .command("insert")
    .description("submit a Markdown archive to Arch0")
    .argument("<markdown_file>", "Markdown file to submit")
    .option("--title <title>", "archive title")
    .option("--from <sender>", "sender identity")
    .option("--instruction <instruction>", "natural-language instruction")
    .option("--server-url <url>", "Arch0 server URL")
    .option("--token <token>", "API token")
    .option("--dry-run", "print payload metadata without sending")
    .option("--json", "print raw JSON response")
    .action(async (markdownFile: string, options: Record<string, unknown>) => {
      process.exitCode = (
        await runInsert(
          markdownFile,
          {
            title: options.title as string | undefined,
            from: options.from as string | undefined,
            instruction: options.instruction as string | undefined,
            serverUrl: options.serverUrl as string | undefined,
            token: options.token as string | undefined,
            dryRun: Boolean(options.dryRun),
            json: Boolean(options.json),
            configPath: rootOptions(program).configPath
          },
          { output }
        )
      ).exitCode;
    });

  program.command("status").description("check Arch0 CLI connectivity").action(async () => {
    process.exitCode = (await runStatus(rootOptions(program), { output })).exitCode;
  });

  program.command("doctor").description("run Arch0 CLI diagnostics").action(async () => {
    process.exitCode = (await runDoctor(rootOptions(program), { output })).exitCode;
  });

  const config = program.command("config").description("show or update CLI config");
  config.command("show").description("show redacted config").action(async () => {
    process.exitCode = (await runConfigShow(rootOptions(program), { output })).exitCode;
  });
  config
    .command("set")
    .description("set a config value")
    .argument("<key>")
    .argument("<value>")
    .action(async (key: string, value: string) => {
      process.exitCode = (await runConfigSet(key, value, rootOptions(program), { output })).exitCode;
    });

  return program;
}

function rootOptions(program: Command): { configPath?: string } {
  const opts = program.opts<{ config?: string }>();
  return { configPath: opts.config };
}

function parseMode(mode: string | undefined): "local" | "remote" | undefined {
  if (mode === undefined) return undefined;
  if (mode === "local" || mode === "remote") return mode;
  throw new Error("setup mode must be local or remote");
}

buildProgram().parseAsync().catch((error: unknown) => {
  output.stderr(`Error: ${(error as Error).message}`);
  process.exitCode = 1;
});
