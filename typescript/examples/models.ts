import { models, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  // No Agent, and no withTask(): asking which models exist starts no Core and
  // spends nothing, so neither a Core executable nor a usage task is needed
  // here. Only auth is.
  const found = await models(config.auth);
  console.log(`${found.length} models available`);
  for (const model of found) {
    console.log(`  ${model.id} (${model.ownedBy ?? 'unknown provider'})`);
  }
  // The ids are exactly what `model` accepts, so a consumer can pick one from
  // this list and hand it straight back.
  if (!found.some(model => model.id === config.model)) {
    console.log(`\nNote: ${config.model} is not in this list.`);
  }
}

if (isMain(import.meta.url)) await main();
