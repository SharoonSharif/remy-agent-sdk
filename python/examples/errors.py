import asyncio
from remy import Agent, RemyError
from config import options, with_task


async def main(config=None):
    config = with_task(options() if config is None else config)
    async with Agent(**config) as agent:
        # "[[fail]]" asks the local smoke peer for a 429. It is an artefact of
        # this repository's offline harness, not SDK syntax -- a real gateway
        # sends one when you are actually rate limited.
        handle = await agent.run("[[fail]] provoke a gateway error")

        # raise_on_error=False returns the RunResult with .error set instead of
        # raising. Prefer it when you intend to inspect the failure; the other
        # examples pass True because they intend to stop.
        result = await handle.result()
        error = result.error
        if error is None:
            raise RuntimeError("expected the run to fail; the peer did not refuse")

        # Four machine-readable facts, which is the point of a typed error:
        # a caller can decide what to do without parsing a message string.
        # Confirmed by testing against this repo's local smoke peer: request_id
        # only populates when the response carries a request-id HEADER -- this
        # peer sends "X-Request-Id"; a request_id field inside the JSON error
        # body is not enough by itself (the peer's body has always carried
        # one, and that alone left this field unset). is_retryable is not
        # header-sourced at all -- it is derived from how the failure is
        # classified (its status/type) -- which is why it arrives populated
        # here independently of any header.
        print(f"code: {error.code}")
        print(f"retryable: {error.is_retryable}")
        print(f"retry_after: {error.retry_after}")
        print(f"request_id: {error.request_id}")

        # is_retryable is the one to branch on. retry_after says how long to
        # wait when it is set; request_id is what a support ticket needs.
        if error.is_retryable:
            print(f"would retry after {error.retry_after or 1}s")
        else:
            print("would not retry: this failure will not resolve on its own")

        # The same error raised, for a caller that would rather catch than check.
        try:
            await handle.result(raise_on_error=True)
        except RemyError as raised:
            print(f"raised as {type(raised).__name__}: {raised.code}")


if __name__ == "__main__":
    asyncio.run(main())
