import { Agent } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted } from './config.ts';

const agent = await Agent.connect(options());
try {
  const handle = await agent.run('Say hello in one short sentence.');
  const result = await handle.result;
  requireCompleted(result);
  console.log(result.text);
} finally {
  await agent.close();
}
