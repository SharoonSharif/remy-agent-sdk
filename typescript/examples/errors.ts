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
    // Confirmed by testing against this repo's local smoke peer: requestId
    // only populates when the response carries a request-id HEADER -- this
    // peer sends "X-Request-Id"; a request_id field inside the JSON error
    // body is not enough by itself (the peer's body has always carried one,
    // and that alone left this field unset). isRetryable is not
    // header-sourced at all -- it is derived from how the failure is
    // classified (its status/type) -- which is why it arrives populated here
    // independently of any header.
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
