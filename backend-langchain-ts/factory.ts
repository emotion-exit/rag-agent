import { ChatOpenRouter } from '@langchain/openrouter';
import { ChatOllama } from '@langchain/ollama';
import dotenv from 'dotenv';

dotenv.config();

type dynamicLLM = {
  basic: ChatOpenRouter | ChatOllama;
  pro: ChatOpenRouter | ChatOllama;
};

let _provider = process.env.PROVIDER || 'openrouter';

console.log(`Using provider: ${_provider}`);

function llmFactory(): dynamicLLM {
  switch (_provider) {
    case 'ollama':
      return {
        basic: new ChatOllama({
          model: process.env.OLLAMA_MODEL as string,
          think: false
        }),
        pro: new ChatOllama({
          model: process.env.OLLAMA_MODEL_PRO as string,
          think: false
        })
      };
    case 'openrouter':
    default:
      return {
        basic: new ChatOpenRouter({
          model: process.env.OPENROUTER_MODEL as string,
          apiKey: process.env.OPENROUTER_API_KEY as string
        }),
        pro: new ChatOpenRouter({
          model: process.env.OPENROUTER_MODEL_PRO as string,
          apiKey: process.env.OPENROUTER_API_KEY as string
        })
      };
  }
}

export { llmFactory };
