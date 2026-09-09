import type { AgentOptions, RunResult } from '@corepass/remy-agent-sdk/agent';

export function options(): AgentOptions {
  const names = ['DEMO_MODEL', 'DEMO_GATEWAY', 'DEMO_TOKEN'] as const;
  const missing = names.filter(name => !process.env[name]?.trim());
  if (missing.length) throw new Error(`Set required environment variables: ${missing.join(', ')}`);
  return {
    model: process.env.DEMO_MODEL!,
    auth: { token: process.env.DEMO_TOKEN!, gateway: process.env.DEMO_GATEWAY! },
  };
}

export function requireCompleted(result: RunResult): void {
  if (result.status !== 'completed') {
    throw new Error(`Run ended with status ${result.status}: ${result.error?.code ?? 'no error code'}`);
  }
}
