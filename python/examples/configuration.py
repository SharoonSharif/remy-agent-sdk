import asyncio
import os
from pathlib import Path
from remy import Agent, ConfigurationError, CoreSpec
from config import options, with_task

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def core_spec_from_env():
    """A CoreSpec built from REMY_CORE, never a hard-coded path.

    core_spec OVERRIDES the executable REMY_CORE names, so a literal path
    would point at someone else's machine -- and would break this repository's
    own smoke run, which works by injecting REMY_CORE. Returning None lets the
    SDK resolve the Core the ordinary way.
    """
    core = (os.environ.get("REMY_CORE") or "").strip()
    if not core:
        return None
    return CoreSpec(core, ("run-module", "src.bridge.core_host"))


async def main(config=None):
    config = with_task(options() if config is None else config)

    # Rejected before anything is spawned, and this is the one parameter whose
    # failure mode is worth showing: a bad permission_mode is a typo, and
    # finding out at construction beats finding out mid-run. Spelled out as
    # model= / auth= rather than **config here, so this file -- whose whole
    # point is naming every construction-time parameter -- also names the two
    # that config supplies literally, instead of only ever splatting them.
    try:
        Agent(model=config["model"], auth=config["auth"], permission_mode="not-a-mode")
    except ConfigurationError as error:
        print(f"rejected at construction: {error}")

    # with_task() already put SANDBOX_TASK_ID into config["env"]; env REPLACES
    # rather than overlays (see config.with_task's docstring), so demonstrating
    # it here means preserving that key while adding to it, not splatting
    # os.environ a second time -- config already has an "env" key, and Agent()
    # rejects a keyword given twice.
    env = {**config["env"], "REMY_EXAMPLE": "configuration"}

    async with Agent(
        **{**config, "env": env},
        # Where the Core resolves relative paths. Defaults to the process's cwd.
        cwd=Path.cwd(),
        # Empty by default -- a blank slate. A string replaces it; a mapping
        # with a preset appends to that preset instead.
        system_prompt="You are terse.",
        # Product behaviour is opt-in. Without this the SDK ships no tools,
        # no project settings and no built-in prompt.
        preset="remy_code",
        # A ceiling on model round trips for one run, not a token budget.
        max_steps=8,
        # FILE paths, resolved to absolute. This is the file channel for
        # settings; inline skills/agents/hooks are the other, and inline
        # REPLACES rather than merges.
        setting_sources=[FIXTURES / "settings.json"],
        # Explicit at their defaults. Lowering handshake_timeout makes a cold
        # Core start look like a failure; lowering command_timeout makes a slow
        # model look like one.
        handshake_timeout=10.0,
        command_timeout=30.0,
        # None here means "resolve the Core normally" -- see the helper above.
        core_spec=core_spec_from_env(),
    ) as agent:
        print(f"configured cwd: {agent.cwd}")
        # preset="remy_code" turns on the SDK's built-in tools (file edits,
        # bash, etc.) -- confirmed here: a run attempted one, and with no
        # can_use_tool callback registered the Core auto-resolved the pending
        # permission to "interrupt" rather than complete (see events.py's
        # docstring for the same mechanism). Configuring the preset is the
        # point of this example; running it to completion is custom_tool.py
        # and events.py's job, which both supply that callback.
        print("configured; not run -- see comment above")


if __name__ == "__main__":
    asyncio.run(main())
