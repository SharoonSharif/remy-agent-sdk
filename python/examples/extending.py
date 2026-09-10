import asyncio
from remy import Agent, PermissionDecision, tool
from config import options, require_completed, with_task


async def main(config=None):
    fired = []
    dispatched = []

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

    # This example is about skills, agents, hooks and MCP -- not permissions --
    # but both hooks above fire regardless: before_run unconditionally, and
    # before_tool before any permission decision is even computed. What the
    # callback actually buys is completion -- without one, the pending
    # multiply call auto-resolves to "interrupt", the run ends as
    # "interrupted", and require_completed() raises before the rest of the
    # example prints. See custom_tool.py for the permission topic itself.
    # Allows BOTH spellings, and records which one the Core actually asked
    # about. That record is what proves which of the two registrations below
    # served the call: a bare "multiply" means the top-level `tools=` path,
    # while "mcp__local__multiply" means the sdk-MCP server. Allowing only
    # the bare name -- as this example first did -- silently denied every
    # namespaced call, so the MCP path could never run.
    async def allow_multiply(name, arguments):
        if name in ("multiply", "mcp__local__multiply"):
            dispatched.append(name)
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
        # List form: each registration names a callback by the name it was
        # registered under in hook_callbacks below -- that lookup is the only
        # thing that makes hook_callbacks reachable. The simpler mapping form,
        #
        #   hooks={"before_run": note_run_start},
        #
        # registers its callables for you automatically and needs no
        # hook_callbacks at all; but its branch of remy._agent's
        # _prepare_hooks never consults hook_callbacks, so a name placed
        # there while hooks stayed a mapping would be accepted at
        # construction and then never invoked.
        # This example demonstrates hook_callbacks, so it uses the list form.
        hooks=[
            {"event": "before_run", "callback": "on_run"},
            {"event": "before_tool", "callback": "on_tool"},
        ],
        # Named callables the list-form registrations above look up by name.
        hook_callbacks={"on_run": note_run_start, "on_tool": note_tool_start},
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
        # asymmetry, not a guess: the TypeScript binding's own Agent.connect()
        # does this wiring FOR you when the tools list holds live Tool
        # objects, which is why extending.ts needs no such hint. Confirmed by
        # reading both the Core's and the TypeScript SDK's source for how an
        # "sdk" MCP tool call is dispatched.
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
        print(f"tool dispatched as: {dispatched[0] if dispatched else 'nothing'}")
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
