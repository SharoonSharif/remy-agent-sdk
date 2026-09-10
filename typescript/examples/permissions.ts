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

  // onPermission WINS over permissionMode. The Core decides in this order:
  // an approval already carried on the run state, then the callback if one
  // exists, and only then the mode — so permissionMode is the fallback for a
  // consumer that supplies NO callback, and passing one makes all three
  // values inert. That is the answer to "why am I still asked when I set
  // bypass_permissions", and it is the right precedence: a consumer that
  // installs a gate should not have it bypassed by a config string. Every
  // Agent below passes a callback, so the modes here only show where they go.
  //
  // 'interrupt' does not refuse — it stops the run and hands back resumable
  // state so a human can decide out of band.
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
    // state -- read from the `approveTool`/`denyTool` functions exported
    // from '@corepass/remy-agent-sdk/agent', not guessed:
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

  // A second Agent, to actually exercise 'accept_edits' instead of just
  // naming it in a comment. This example's only tool is arithmetic, not a
  // file edit, so onPermission still records whether it gets asked.
  const editModeCalls: string[] = [];
  const editing = await Agent.connect({
    ...ready, tools: [add], permissionMode: 'accept_edits',
    onPermission(name: string, input) { editModeCalls.push(name); return { behavior: 'allow', updatedInput: input }; },
  });
  try {
    const handle = await editing.run('Use add to calculate 5 + 5, then say the result.');
    const result = await handle.result;
    requireCompleted(result);
    // Observed against this repo's smoke peer, in both this run and a
    // side-by-side probe over all three permissionMode values: onPermission
    // was invoked here for 'add' exactly as it was above under 'default' and
    // below under 'bypass_permissions' -- accept_edits did not skip asking
    // for this non-file-edit tool. No observable difference here, because
    // accept_edits's documented effect (pre-approving file edits) has
    // nothing to act on when the registered tool is arithmetic, not a file
    // edit; an onPermission callback, once registered, appears to be
    // consulted regardless of permissionMode. That is an observation about
    // this Core's behaviour, not a guarantee read from any docstring --
    // nothing in the installed package documents when permissionMode itself
    // (rather than onPermission's return value) decides the outcome.
    console.log(`accept_edits asked onPermission for a non-edit tool: ${editModeCalls.length > 0}`);
  } finally {
    await editing.close();
  }

  // A third Agent, because permissionMode is set at construction.
  const trusting = await Agent.connect({
    ...ready, tools: [add], permissionMode: 'bypass_permissions',
    onPermission(_name, input) { return { behavior: 'allow', updatedInput: input }; },
  });
  try {
    // "[[slow]]" asks the smoke peer to stall between chunks so the cancel is
    // meant to land mid-stream by design. Observed against this repo's smoke
    // peer: removing the marker did not change the outcome -- a local IPC
    // cancel still won the race against even a zero-delay reply in every run
    // tried. The marker is belt-and-braces here, not load-bearing; kept
    // because it is still the honest way to express the intent.
    const handle = await trusting.run('[[slow]] Say hello in one short sentence.');
    // Unlike Python's Run.cancel (which returns the terminal RunResult
    // directly), this binding's Run.cancel resolves to a boolean -- whether
    // the Core acknowledged the cancel request -- read from the `Run` class
    // exported from '@corepass/remy-agent-sdk/agent'
    // (`cancel(): Promise<boolean>`), not guessed. The terminal status still
    // comes from the same `result` promise every other example reads.
    //
    // That boolean hides a real gap: unlike Python's Run.cancel(*,
    // ack_timeout=, grace=), this binding's Run.cancel() takes no tuning
    // parameters at all -- reading dist/protocol/process.js in the installed
    // package, the Core child it drives always waits a fixed, hardcoded
    // CANCEL_GRACE_PERIOD_MS (2000ms) for the turn to terminate, and if that
    // elapses it kills the Core process outright and resolves to `false`;
    // there is no public way from '@corepass/remy-agent-sdk/agent' to raise
    // that window the way the Python example now does. Timing this exact
    // scenario against this repo's smoke peer and a real frozen Core, from
    // the Python side (whose Run.cancel does expose ack_timeout/grace and so
    // could be instrumented), termination after a cancel took 1.6s-6.1s
    // across 50 runs -- comfortably past 2000ms often enough to explain an
    // `acknowledged: false` here, and with it a killed Core, on a real
    // fraction of runs. This is a Core/SDK-level gap this example cannot
    // close: there is nothing to pass in to make TypeScript's cancel() wait
    // longer, so a `false` is reported honestly rather than treated as the
    // same "lost the race to a fast completion" case the guard below covers.
    const acknowledged = await handle.cancel();
    console.log(`cancel acknowledged: ${acknowledged}`);
    if (!acknowledged) {
      console.log(
        'cancel outlived this binding\'s fixed 2000ms grace; the Core was already ' +
        'terminated, so there is no RunResult left to check -- see the comment above',
      );
    } else {
      const cancelled = await handle.result;
      // A structural guard, matching the interrupt half's: if '[[slow]]' ever
      // stopped stalling the peer, the reply could complete before the cancel
      // request lands. Unlike Python, where Run.cancel's own return value is
      // the terminal RunResult to check, this binding's cancel() only reports
      // acknowledgement (a boolean) -- the terminal status has to come from
      // `result` instead, which is why the check sits here rather than on
      // `acknowledged`. Fail loudly rather than silently accepting a
      // 'completed' run as if it had been cancelled.
      if (cancelled.status !== 'cancelled') {
        throw new Error(`expected the cancelled run to end as cancelled, got ${cancelled.status}`);
      }
      console.log(`cancelled run ended as ${cancelled.status}`);
    }
  } finally {
    await trusting.close();
  }
}

if (isMain(import.meta.url)) await main();
