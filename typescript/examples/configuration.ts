import { Agent, SDKError, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, withTask, isMain } from './config.ts';

const FIXTURES = new URL('./fixtures/', import.meta.url);

/**
 * `process` block built from REMY_CORE, never a hard-coded path.
 *
 * `process.command` overrides the executable REMY_CORE names, so a literal
 * path would point at someone else's machine — and would break this
 * repository's own smoke run, which works by injecting REMY_CORE. Undefined
 * lets the SDK resolve the Core the ordinary way.
 */
function processFromEnv(): AgentOptions['process'] {
  const core = process.env.REMY_CORE?.trim();
  return core ? { command: core, args: ['run-module', 'src.bridge.core_host'] } : undefined;
}

export async function main(config: AgentOptions = options()): Promise<void> {
  const ready = await withTask(config);

  // Rejected before anything is spawned: a bad permissionMode is a typo, and
  // finding out at construction beats finding out mid-run.
  try {
    await Agent.connect({ ...ready, permissionMode: 'not-a-mode' as never });
  } catch (error) {
    console.log(`rejected at construction: ${(error as SDKError).message}`);
  }

  const agent = await Agent.connect({
    ...ready,
    // Where the Core resolves relative paths. Defaults to process.cwd().
    cwd: process.cwd(),
    // Empty by default -- a blank slate. A string replaces it; an object
    // with a preset appends to that preset instead.
    systemPrompt: 'You are terse.',
    // Product behaviour is opt-in. Without this the SDK ships no tools, no
    // project settings and no built-in prompt.
    preset: 'remy_code',
    // A ceiling on model round trips for one run, not a token budget.
    maxSteps: 8,
    // FILE paths. This is the file channel for settings; inline
    // skills/agents/hooks is the other, and inline REPLACES rather than
    // merges.
    settingSources: [new URL('settings.json', FIXTURES).pathname],
    // A callback (permission/hook/session-store) timeout, not a connection
    // timeout -- see `process` below for the two that are.
    callbackTimeoutMs: 30_000,
    process: {
      ...ready.process,
      ...processFromEnv(),
      // Explicit at their defaults. Lowering handshakeTimeoutMs makes a cold
      // Core start look like a failure; lowering commandTimeoutMs makes a
      // slow model look like one. These are the real counterparts of
      // Python's handshake_timeout/command_timeout -- not top-level
      // AgentOptions fields as the plan first guessed, but ConnectOptions
      // fields nested under `process` (SpawnCoreOptions extends
      // ConnectOptions, and AgentOptions.process is (almost) a
      // SpawnCoreOptions).
      handshakeTimeoutMs: 10_000,
      commandTimeoutMs: 30_000,
    },
  });
  try {
    console.log(`configured cwd: ${process.cwd()}`);
    // preset: 'remy_code' turns on the SDK's built-in tools (file edits,
    // bash, etc.) -- confirmed in the Python binding's version of this
    // example: a run attempted one, and with no onPermission callback
    // registered the Core auto-resolved the pending permission to
    // "interrupt" rather than complete (see events.ts's comment for the same
    // mechanism). Configuring the preset is the point of this example;
    // running it to completion is custom-tool.ts and events.ts's job, which
    // both supply that callback.
    console.log('configured; not run -- see comment above');
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
