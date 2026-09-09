import { Agent } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted } from './config.ts';

let calls = 0;
const agent = await Agent.connect({
  ...options(),
  tools: [{
    name: 'add', description: 'Add two integers and return their sum.',
    inputSchema: {
      type: 'object', properties: { a: { type: 'integer' }, b: { type: 'integer' } },
      required: ['a', 'b'], additionalProperties: false,
    },
    execute(input) {
      const a = input.a, b = input.b;
      if (typeof a !== 'number' || typeof b !== 'number' || !Number.isInteger(a) || !Number.isInteger(b)) {
        throw new Error('add requires two integers');
      }
      calls++;
      console.log(`Local add(${a}, ${b}) = ${a + b}`);
      return a + b;
    },
  }],
  onPermission(name, input) {
    return name === 'add' ? { behavior: 'allow', updatedInput: input } : { behavior: 'deny' };
  },
});
try {
  const handle = await agent.run('Use the add tool to calculate 2 + 3, then tell me its result.');
  const result = await handle.result;
  requireCompleted(result);
  if (!calls) throw new Error('The model did not call add; try a tool-capable model.');
  console.log(result.text);
} finally {
  await agent.close();
}
