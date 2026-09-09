import { Agent, type AgentOptions, type Tool } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

const multiply: Tool = {
  name: 'multiply', description: 'Multiply two integers and return their product.',
  inputSchema: {
    type: 'object', properties: { a: { type: 'integer' }, b: { type: 'integer' } },
    required: ['a', 'b'], additionalProperties: false,
  },
  execute(input) { return Number(input.a) * Number(input.b); },
};

export async function main(config: AgentOptions = options()): Promise<void> {
  const fired: string[] = [];
  const agent = await Agent.connect({
    ...(await withTask(config)),
    // Inline, and inline REPLACES rather than merges. Shape verified against
    // the Core (not guessed): Python's probe against the same Core rejected
    // an "instructions" key for a skill body with "SkillEntry.__init__() got
    // an unexpected keyword argument 'instructions'" -- the key it wants is
    // "content". The SDK only checks that the options object serializes.
    skills: { greet: { description: 'Greet in one line.', content: 'Reply with a greeting.' } },
    agents: { summarizer: { description: 'Summarize text.', prompt: 'Summarize briefly.' } },
    // Hooks run in THIS process, like tools and permission callbacks. The
    // real Hook type, exported from '@corepass/remy-agent-sdk/agent', is a
    // union of CallbackHook ({event, callback, name?}) and CommandHook
    // ({event, command, timeout?})
    // -- always a LIST of these, never the Python binding's {event: callable}
    // mapping. Valid events are the same four as Python: before_run,
    // after_run, before_tool, after_tool. AgentOptions has no hookCallbacks
    // field at all: the list-form callback IS the function, so there is no
    // separate registry of named callables for it to point at. That is a
    // real asymmetry with Python's hook_callbacks, not an oversight here.
    hooks: [{
      event: 'before_run',
      callback: () => { fired.push('before_run'); console.log('before_run hook fired'); },
    }],
    // An in-process MCP server: no subprocess, no URL, no dependency. Unlike
    // Python's descriptor()-only wire format, TypeScript's MCPServer type
    // wants the live Tool objects here (same ones `tools` takes), because
    // this binding's AgentOptions is never JSON-round-tripped the way the
    // Python client snapshots its options -- the callable travels with it.
    mcpServers: { local: { type: 'sdk', tools: [multiply] } },
    tools: [multiply],
    // This example is about skills, agents, hooks and MCP -- not permissions
    // -- but the before_run hook above fires regardless, unconditionally at
    // the start of the run. What onPermission actually buys is completion --
    // without it, the pending multiply call auto-resolves to "interrupt",
    // the run ends as "interrupted", and requireCompleted() raises before
    // the rest of the example prints. See custom-tool.ts for the permission
    // topic itself.
    onPermission(name, input) {
      return name === 'multiply' ? { behavior: 'allow', updatedInput: input } : { behavior: 'deny' };
    },
  });
  try {
    const handle = await agent.run('Use multiply to calculate 6 * 7, then say the result.');
    const result = await handle.result;
    requireCompleted(result);
    console.log(`hooks fired: ${fired.join(', ')}`);
    console.log(result.text);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
