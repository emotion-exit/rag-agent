import { ChatOpenRouter } from '@langchain/openrouter';
import { ChatOllama } from '@langchain/ollama';
import dotenv from 'dotenv';

dotenv.config();

let _provider = 'openrouter';

function llmFactory(provider: string): ChatOpenRouter | ChatOllama {
  _provider = provider;
  switch (_provider) {
    case 'ollama':
      return new ChatOllama({
        model: process.env.OLLAMA_MODEL as string,
        think: false
      });
    case 'openrouter':
    default:
      return new ChatOpenRouter({
        model: process.env.OPENROUTER_MODEL as string,
        apiKey: process.env.OPENROUTER_API_KEY as string
      });
  }
}

export { llmFactory };
