import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import type { AgentOptions, RunResult } from '@corepass/remy-agent-sdk/agent';

export function options(): AgentOptions {
  const names = ['DEMO_MODEL', 'DEMO_TOKEN'] as const;
  const missing = names.filter(name => !process.env[name]?.trim());
  if (missing.length) throw new Error(`Set required environment variables: ${missing.join(', ')}`);
  return {
    model: process.env.DEMO_MODEL!,
    auth: { token: process.env.DEMO_TOKEN!, gateway: 'https://api.corepass.com/edge/v1' },
  };
}

export function requireCompleted(result: RunResult): void {
  if (result.status !== 'completed') {
    throw new Error(`Run ended with status ${result.status}: ${result.error?.code ?? 'no error code'}`);
  }
}

export function isMain(url: string): boolean {
  return !!process.argv[1] && fileURLToPath(url) === resolve(process.argv[1]);
}
