import { Agent, approveTool, denyTool, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

const add = {
  name: 'add', description: 'Add two integers and return their sum.',
  inputSchema: {
    type: 'object', properties: { a: { type: 'integer' }, b: { type: 'integer' } },
    required: ['a', 'b'], additionalProperties: false,
  },
  execute(input: Record<string, unknown>) {
    const sum = Number(input.a) + Number(input.b);
    console.log(`Local add(${input.a}, ${input.b}) = ${sum}`);
    return sum;
  },
};

export async function main(config: AgentOptions = options()): Promise<void> {
  const ready = await withTask(config);

  // permissionMode is the standing policy; onPermission is the per-call
  // question. 'interrupt' does not refuse — it stops the run and hands back
  // resumable state so a human can decide out of band.
  const asking = await Agent.connect({
    ...ready, tools: [add], permissionMode: 'default',
    onPermission() { return { behavior: 'interrupt', message: 'a human should approve this' }; },
  });
  try {
    const handle = await asking.run('Use add to calculate 2 + 3, then say the result.');
    console.log(`status while running: ${handle.status}`);
    const interrupted = await handle.result;
    const state = interrupted.runState;
    if (!state) throw new Error('expected an interrupt to produce resumable state');

    // Plain serializable data, so the pause can outlive the process.
    console.log(`interrupted with ${JSON.stringify(state).length} bytes of resumable state`);

    // approveTool / denyTool build the approval; the Python binding spells
    // this `RunState.with_approval`. Unlike the Python method, approveTool
    // takes the tool call id as its own argument rather than a method on the
    // state -- read from dist/protocol/agent/run.d.ts, not guessed:
    // `approveTool(state, toolCallId, updatedInput?)`. The id itself lives
    // under the same "pending_tool_calls[].id" key the Python example
    // dumped from this repo's Core.
    const pending = state.pending_tool_calls ?? [];
    if (pending.length === 0) throw new Error(`no pending call in state: ${Object.keys(state)}`);
    const resumed = await asking.run('', { runState: approveTool(state, pending[0].id) });
    const result = await resumed.result;
    requireCompleted(result);
    console.log(`resumed after approval: ${result.status}`);
    console.log(`denyTool is the other half: ${typeof denyTool}`);
  } finally {
    await asking.close();
  }

  // A second Agent, because permissionMode is set at construction.
  const trusting = await Agent.connect({
    ...ready, tools: [add], permissionMode: 'bypass_permissions',
    onPermission(_name, input) { return { behavior: 'allow', updatedInput: input }; },
  });
  try {
    // "[[slow]]" makes the smoke peer stall between chunks: a reply that has
    // already finished cannot be cancelled.
    const handle = await trusting.run('[[slow]] Say hello in one short sentence.');
    // Unlike Python's Run.cancel (which returns the terminal RunResult
    // directly), this binding's Run.cancel resolves to a boolean -- whether
    // the Core acknowledged the cancel request -- read from run.d.ts
    // (`cancel(): Promise<boolean>`), not guessed. The terminal status still
    // comes from the same `result` promise every other example reads.
    const acknowledged = await handle.cancel();
    console.log(`cancel acknowledged: ${acknowledged}`);
    const cancelled = await handle.result;
    console.log(`cancelled run ended as ${cancelled.status}`);
  } finally {
    await trusting.close();
  }
}

if (isMain(import.meta.url)) await main();
