import { Agent, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  const agent = await Agent.connect(config);
  try {
    const handle = await agent.run('Say hello in one short sentence.');
    const result = await handle.result;
    requireCompleted(result);
    console.log(result.text);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
