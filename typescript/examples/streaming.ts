import { Agent, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  const agent = await Agent.connect(config);
  try {
    const handle = await agent.run('Explain what an SDK is in two short sentences.');
    for await (const event of handle) {
      if (event.type === 'assistant.text_delta') process.stdout.write(event.text);
    }
    const result = await handle.result;
    requireCompleted(result);
    console.log('\nUsage:', result.usage);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
