import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import type { AgentOptions, RunResult } from '@corepass/remy-agent-sdk/agent';

export const GATEWAY = 'https://dev-api.corepass.com/edge/v1';

/**
 * Fill in DEMO_* from `typescript/.env`, WITHOUT overriding what is set.
 *
 * Not overriding is the load-bearing half, and `process.loadEnvFile` already
 * behaves that way. `scripts/smoke.py` runs these examples against a local
 * fake model peer by injecting `DEMO_*` into the child environment; if a
 * developer's real `.env` won here, the smoke run would authenticate with a
 * real token against the real gateway and stop being the offline check it
 * advertises. A shell that exported something on purpose wins for the same
 * reason.
 *
 * Node's built-in rather than a dotenv package: these examples are published
 * to show what integrating the SDK costs, and one convenience is not worth a
 * dependency in that answer. Requires Node 20.12+, below this repo's floor.
 */
function loadEnvFile(): void {
  try {
    process.loadEnvFile(new URL('../.env', import.meta.url));
  } catch {
    // No .env is the normal case for a consumer who exports in the shell.
  }
}

export function options(): AgentOptions {
  loadEnvFile();
  const names = ['DEMO_MODEL', 'DEMO_TOKEN', 'DEMO_PRODUCT_ID'] as const;
  const missing = names.filter(name => !process.env[name]?.trim());
  if (missing.length) throw new Error(`Set required environment variables: ${missing.join(', ')}`);
  return {
    model: process.env.DEMO_MODEL!,
    auth: { token: process.env.DEMO_TOKEN!, gateway: GATEWAY },
  };
}

/**
 * Open a usage task and put its id where the Core will look for it.
 *
 * The bearer is a `cpst2` SERVICE credential, not a user's own token, and the
 * gateway runs task attribution in enforce mode: a service-authenticated call
 * carries no live session to bill, so it must name the task that authorized
 * the spend or the request is rejected with 400 `metadata.task_id is required`.
 *
 * The id travels by ENVIRONMENT rather than an SDK argument, because the Core
 * is what talks to the gateway — it reads `SANDBOX_TASK_ID` and copies the
 * value into `metadata.task_id` on every model call.
 *
 * `process.env` OVERLAYS the parent's environment, so only the one key is
 * named here. The Python binding's `env` replaces it instead and has to splat
 * `os.environ` — same contract, different spelling.
 */
export async function withTask(config: AgentOptions): Promise<AgentOptions> {
  return {
    ...config,
    process: { ...config.process, env: { ...config.process?.env, SANDBOX_TASK_ID: await openTask(config) } },
  };
}

/**
 * Mint a task id from the gateway, or throw with the reason it refused.
 *
 * `product_id` must be one of the audiences the service token was issued for —
 * the gateway checks exact membership, so a token audienced only for its own
 * service name cannot open a task for any product. `system` books the spend to
 * the service itself; naming a user instead takes both `user_id` and
 * `tenant_id` and a token carrying `attribute_for_others`.
 */
async function openTask(config: AgentOptions): Promise<string> {
  const response = await fetch(`${config.auth.gateway}/tasks`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${config.auth.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: process.env.DEMO_PRODUCT_ID, system: true }),
    signal: AbortSignal.timeout(10_000),
  });
  // The body says which of product_id/user_id/tenant_id the gateway objected
  // to. Reporting only the status leaves nothing to act on.
  if (!response.ok) {
    throw new Error(`Could not open a usage task (${response.status}): ${await response.text()}`);
  }
  const { task_id: taskId } = (await response.json()) as { task_id?: string };
  if (!taskId) throw new Error('The gateway opened a task but returned no task_id');
  return taskId;
}

export function requireCompleted(result: RunResult): void {
  if (result.status !== 'completed') {
    throw new Error(`Run ended with status ${result.status}: ${result.error?.code ?? 'no error code'}`);
  }
}

export function isMain(url: string): boolean {
  return !!process.argv[1] && fileURLToPath(url) === resolve(process.argv[1]);
}
