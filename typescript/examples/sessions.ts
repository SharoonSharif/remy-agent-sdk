import { Agent, MemorySessionStore, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  // An in-memory cache of snapshots, and explicitly NOT an authority: the Core
  // owns session state. The Python binding spells this `SessionStore`.
  const store = new MemorySessionStore();
  const agent = await Agent.connect({ ...(await withTask(config)), sessionStore: store });
  try {
    // agent.sessions is the collection; a Session is the handle.
    const session = await agent.sessions.create();
    console.log(`session ${session.id}`);

    // Session has no `run` -- `resume` is how you advance the same session,
    // by session id, rather than starting a fresh one.
    const first = await session.resume('Say hello in one short sentence.');
    requireCompleted(await first.result);

    // Same session, so the Core sends the accumulated history. The peer echoes
    // the turn count, which is how "it continued" is observable rather than
    // assumed.
    const second = await session.resume('And again, please.');
    const result = await second.result;
    requireCompleted(result);
    console.log(`second turn saw ${result.text.trim().split(/\s+/).pop()}`);

    // refresh() re-reads from the Core, the authority, and updates this
    // Session object in place; it hands back the plain snapshot rather than a
    // new Session, so `session` itself stays the handle to keep using.
    const snapshot = await session.refresh();
    console.log(`${snapshot.messages.length} messages after two turns`);

    // fork() branches: the original keeps its history, the copy starts from
    // it. Use it to try two continuations without losing the first.
    const branch = await session.fork();
    console.log(`forked ${session.id} -> ${branch.id}`);

    // The snapshot is plain data, so a consumer can persist it anywhere. This
    // is the shape sessionStore caches.
    console.log(`snapshot keys: ${Object.keys(session.snapshot).sort().join(', ')}`);

    // Every session the store saw, for a consumer listing conversations. list()
    // is async here, unlike Python's synchronous SessionStore.list() -- another
    // naming/behavior asymmetry between the two bindings' stores.
    console.log(`store holds ${(await store.list()).length} snapshot(s)`);

    // get() reads back one cached snapshot by id -- a read-back of what was
    // cached locally, not a substitute for the Core's authority over session
    // state; refresh() above is what re-reads the real thing.
    const cached = await store.get(session.id);
    console.log(`cached snapshot has ${cached?.messages.length} message(s)`);

    // A session id is enough to resume in a later process -- the Core still
    // has the state, so nothing needs to be carried but the id.
    const resumed = await agent.sessions.get(session.id);
    console.log(`resumed ${resumed.id}`);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
