import { Agent, SDKError, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, withTask, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  const agent = await Agent.connect(await withTask(config));
  try {
    // "[[fail]]" asks the local smoke peer for a 429. It is an artefact of
    // this repository's offline harness, not SDK syntax.
    const handle = await agent.run('[[fail]] provoke a gateway error');
    const result = await handle.result;
    const error = result.error;
    if (!error) throw new Error('expected the run to fail; the peer did not refuse');

    // Machine-readable facts, so a caller can decide without parsing a string.
    // The Python binding spells `is_retryable`; here it is `isRetryable`.
    // Observed against this repo's local smoke peer: code, isRetryable and
    // retryAfter all arrive populated, but requestId prints as undefined here
    // -- the peer's 429 body carries a request_id, but nothing in that
    // response is a request-id HEADER, and undefined is what shows up on the
    // caught error. A real gateway that returns one should populate it.
    console.log(`code: ${error.code}`);
    console.log(`retryable: ${error.isRetryable}`);
    console.log(`retry_after: ${error.retryAfter}`);
    console.log(`request_id: ${error.requestId}`);

    if (error.isRetryable) {
      console.log(`would retry after ${error.retryAfter ?? 1}s`);
    } else {
      console.log('would not retry: this failure will not resolve on its own');
    }
    console.log(`SDKError is the thrown form: ${SDKError.name}`);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
