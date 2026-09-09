import asyncio
import json
from remy import Agent, SessionStore
from config import options, require_completed, with_task


async def main(config=None):
    config = with_task(options() if config is None else config)

    # An in-memory cache of snapshots, and explicitly NOT an authority: the
    # Core owns session state. Pass your own to inspect what was cached;
    # omit it and the Agent makes one.
    store = SessionStore()

    async with Agent(**config, session_store=store) as agent:
        # agent.sessions is the collection; a Session is the handle.
        session = await agent.sessions.create()
        print(f"session {session.session_id}")

        first = await session.run("Say hello in one short sentence.")
        result = await first.result(raise_on_error=True)
        require_completed(result)

        # Same session, so the Core sends the accumulated history. The peer
        # echoes the turn count, which is how "it continued" is observable
        # rather than assumed.
        second = await session.run("And again, please.")
        result = await second.result(raise_on_error=True)
        require_completed(result)
        print(f"second turn saw {result.text.strip().split()[-1]}")

        # refresh() re-reads from the Core, the authority. The local Session
        # object is a snapshot and goes stale the moment a run advances it.
        session = await session.refresh()
        print(f"{len(session.messages)} messages after two turns")

        # fork() branches: the original keeps its history, the copy starts from
        # it. Use it to try two continuations without losing the first.
        branch = await session.fork()
        print(f"forked {session.session_id} -> {branch.session_id}")

        # The snapshot is plain data, so a consumer can persist it anywhere.
        # This is the shape session_store caches.
        print(f"snapshot keys: {sorted(json.loads(json.dumps(session.snapshot)))}")

        # Every session the store saw, for a consumer listing conversations.
        print(f"store holds {len(store.list())} snapshot(s)")

        # A session id is enough to resume in a later process -- the Core still
        # has the state, so nothing needs to be carried but the id.
        resumed = await agent.sessions.get(session.session_id)
        print(f"resumed {resumed.session_id}")


if __name__ == "__main__":
    asyncio.run(main())
