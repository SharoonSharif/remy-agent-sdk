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
    // This example is about events, not permissions -- but the permission
    // decision is NOT incidental to which events you see, unlike in
    // extending.ts. Verified by removing this callback: the transcript
    // stops dead after the tool-call turn's usage event (seq 4-12, 9 events)
    // with no tool event and no text delta, because the pending "add" call
    // auto-resolves to "interrupt" -- requireCompleted() then raises before
    // the loop or the final log ever see the rest. With the callback
    // allowing "add", the run continues through the tool call and a second
    // model turn (seq up to 28), so the callback is what makes the tool and
    // text-delta branches below fire at all, not only what makes the run
    // end "completed". See custom-tool.ts for the permission topic itself.
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
