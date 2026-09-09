import { run, SDK_API_VERSION, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  // Says which contract this binding speaks. Log it when reporting a bug:
  // "it does not work" and "it speaks a different SDK API version than the
  // one you are reading about" are different reports.
  //
  // The Python side also logs PROTOCOL_NAME/PROTOCOL_VERSION alongside
  // SDK_API_VERSION. The '@corepass/remy-agent-sdk/agent' entry point this
  // example imports from re-exports only SDK_API_VERSION (see
  // dist/protocol/agent/index.d.ts), so there is no TypeScript counterpart to
  // import here rather than reach into '@corepass/remy-agent-sdk/protocol'.
  console.log(`SDK API v${SDK_API_VERSION}`);

  // run() is one prompt with no Agent to manage: it constructs one, runs, and
  // closes it. Use it when there is no second turn.
  const result = await run('Say hello in one short sentence.', await withTask(config));
  requireCompleted(result);
  console.log(result.text);
}

if (isMain(import.meta.url)) await main();
