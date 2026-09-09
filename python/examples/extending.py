import asyncio
from remy import Agent, PermissionDecision, tool
from config import options, require_completed, with_task


async def main(config=None):
    fired = []

    @tool
    def multiply(a: int, b: int) -> int:
        """Multiply two integers and return their product."""
        return a * b

    def note_run_start(context):
        # Hooks run in THIS process, like tools and permission callbacks. The
        # Core asks; your code answers. Valid events are exactly before_run,
        # after_run, before_tool and after_tool -- any other name is a
        # ConfigurationError at construction.
        fired.append("before_run")
        print("before_run hook fired")

    def note_tool_start(context):
        fired.append("before_tool")
        print("before_tool hook fired")

    async def allow_multiply(name, arguments):
        if name == "multiply":
            return PermissionDecision("allow", updated_input=arguments)
        return PermissionDecision("deny")

    config = with_task(options() if config is None else config)
    async with Agent(
        **config,
        # Inline, and inline REPLACES rather than merges -- passing skills here
        # does not add to whatever setting_sources loaded. Shape verified
        # against the Core (not guessed): a first attempt with "instructions"
        # raised "SkillEntry.__init__() got an unexpected keyword argument
        # 'instructions'" straight from the Core. The key the Core's
        # SkillEntry actually takes for the skill body is "content" (renamed
        # internally to "body"); the SDK itself only checks
        # JSON-serializability and would have let "instructions" through.
        skills={"greet": {
            "description": "Greet in one line.",
            "content": "Reply with a greeting.",
        }},
        # Sub-agents the Core may delegate to, declared the same way.
        agents={"summarizer": {
            "description": "Summarize text.",
            "prompt": "Summarize briefly.",
        }},
        # Mapping form: the callables are registered for you. The list form
        # ({"event": ..., "callback": "name"}) refers to names you registered
        # yourself through hook_callbacks, which is the next parameter.
        hooks={"before_run": note_run_start},
        # Named callables a list-form registration can point at. Shown together
        # with the mapping form above because the two are alternatives and the
        # difference is only where the name comes from.
        hook_callbacks={"on_tool": note_tool_start},
        # An in-process MCP server: no subprocess, no URL, no dependency. The
        # tools list wants the same JSON descriptor .descriptor() produces for
        # the top-level `tools` wire format, NOT a live Tool object -- the
        # whole options dict is JSON round-tripped at construction, so a
        # callable in here would fail JSON-serializability.
        #
        # The Core exposes an "sdk" MCP tool to the model under a NAMESPACED
        # name, "mcp__local__multiply" here, and by default routes its
        # callback request back under that same namespaced name -- which
        # nothing in this process answers to, since `tools=` below registers
        # the callable as plain "multiply". An explicit "callback" naming the
        # already-registered tool is what actually connects the two; without
        # it, a model that calls the namespaced tool gets back "unregistered
        # tool 'mcp__local__multiply'". This is a real Python/TypeScript
        # asymmetry, not a guess: the TypeScript binding's own compiled source
        # (dist/protocol/agent/agent.js) does this wiring FOR you when the
        # tools list holds live Tool objects, which is why extending.ts needs
        # no such hint. Confirmed by reading both the Core's and the
        # TypeScript SDK's source for how an "sdk" MCP tool call is dispatched.
        mcp_servers={"local": {"type": "sdk", "tools": [
            {**multiply.descriptor(), "callback": "multiply"},
        ]}},
        tools=[multiply],
        can_use_tool=allow_multiply,
    ) as agent:
        handle = await agent.run("Use multiply to calculate 6 * 7, then say the result.")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        print(f"hooks fired: {fired}")
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
