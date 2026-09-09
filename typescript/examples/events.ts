import { Agent, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  const agent = await Agent.connect({
    ...(await withTask(config)),
    tools: [{
      name: 'add', description: 'Add two integers and return their sum.',
      inputSchema: {
        type: 'object', properties: { a: { type: 'integer' }, b: { type: 'integer' } },
        required: ['a', 'b'], additionalProperties: false,
      },
      execute(input) { return Number(input.a) + Number(input.b); },
    }],
    onPermission(name, input) {
      return name === 'add' ? { behavior: 'allow', updatedInput: input } : { behavior: 'deny' };
    },
  });
  try {
    // "[[thinking]]" asks the local smoke peer for a reasoning delta. It is an
    // artefact of this repository's offline harness, not SDK syntax.
    const handle = await agent.run('[[thinking]] Use add to calculate 2 + 3.');
    for await (const event of handle) {
      // An SDKEvent carries its envelope fields flat (runId, attemptId, seq,
      // origin) rather than nested under a separate `envelope` property, and
      // the raw payload -- not a typed field -- is where a tool's own name
      // lives.
      const seq = event.seq;
      switch (event.type) {
        case 'assistant.thinking_delta': console.log(`thinking delta seq=${seq}: ${event.text}`); break;
        case 'assistant.text_delta': console.log(`text delta seq=${seq}: ${event.text}`); break;
        case 'tool.started': console.log(`tool event seq=${seq}: ${event.payload.name}`); break;
        case 'usage.updated': console.log(`usage event seq=${seq}:`, event.usage); break;
        default: console.log(`${event.type} seq=${seq}`);
      }
    }
    const result = await handle.result;
    requireCompleted(result);
    console.log(`run ${result.runId} finished as ${result.status}`);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
