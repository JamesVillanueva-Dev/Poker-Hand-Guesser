import { existsSync } from "node:fs";
import { join } from "node:path";
import { spawn, spawnSync } from "node:child_process";

const root = process.cwd();
const isWindows = process.platform === "win32";
const localPython = join(root, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
const python = existsSync(localPython) ? localPython : "python";
let shuttingDown = false;

const frontendCommand = isWindows
  ? {
      name: "frontend",
      command: process.env.ComSpec ?? "cmd.exe",
      args: ["/d", "/s", "/c", "npm --prefix frontend run dev"],
      cwd: root,
    }
  : {
      name: "frontend",
      command: "npm",
      args: ["--prefix", "frontend", "run", "dev"],
      cwd: root,
    };

const commands = [
  {
    name: "backend",
    command: python,
    args: ["-m", "uvicorn", "backend.main:app", "--reload"],
    cwd: root,
  },
  frontendCommand,
];

const children = [];

for (const { name, command, args, cwd } of commands) {
  let child;
  try {
    child = spawn(command, args, {
      cwd,
      stdio: ["inherit", "pipe", "pipe"],
      shell: false,
    });
  } catch (error) {
    console.error(`[${name}] failed to start: ${error.message}`);
    shutdown(1);
    continue;
  }

  children.push(child);

  child.stdout.on("data", (data) => writeLines(name, data, process.stdout));
  child.stderr.on("data", (data) => writeLines(name, data, process.stderr));

  child.on("exit", (code, signal) => {
    if (shuttingDown) return;
    console.error(`[${name}] stopped with ${signal ?? `code ${code}`}`);
    shutdown(code ?? 1);
  });

  child.on("error", (error) => {
    if (shuttingDown) return;
    console.error(`[${name}] failed to start: ${error.message}`);
    shutdown(1);
  });
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

function writeLines(name, chunk, stream) {
  for (const line of chunk.toString().split(/\r?\n/)) {
    if (line.trim().length > 0) {
      stream.write(`[${name}] ${line}\n`);
    }
  }
}

function shutdown(exitCode) {
  shuttingDown = true;
  for (const child of children) {
    if (child.killed) {
      continue;
    }
    if (isWindows && child.pid) {
      spawnSync("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
    } else {
      child.kill("SIGTERM");
    }
  }
  setTimeout(() => process.exit(exitCode), 250);
}
