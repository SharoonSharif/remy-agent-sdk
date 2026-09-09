import { Agent } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted } from './config.ts';

const agent = await Agent.connect(options());
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
