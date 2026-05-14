import { ChatGoogle } from '@langchain/google';
import { ChatOpenRouter } from '@langchain/openrouter';
import { ChatOllama } from '@langchain/ollama';
import dotenv from 'dotenv';
import { ProxyAgent, setGlobalDispatcher } from 'undici';

dotenv.config();

const USE_PROXY = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
const PROXY_AGENT = new ProxyAgent(process.env.HTTPS_PROXY as string);

type dynamicLLM = {
  basic: ChatOpenRouter | ChatOllama | ChatGoogle;
  pro: ChatOpenRouter | ChatOllama | ChatGoogle;
};

const _provider = process.env.PROVIDER || 'openrouter';

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
    case 'google':
      if (USE_PROXY) {
        // 让Google模型走代理，解决国内访问问题
        setGlobalDispatcher(PROXY_AGENT);
      }
      return {
        basic: new ChatGoogle({
          model: process.env.GOOGLE_MODEL as string,
          thinkingBudget: 0
        }),
        pro: new ChatGoogle({
          model: process.env.GOOGLE_MODEL_PRO as string,
          thinkingBudget: 0
        })
      };
    case 'openrouter':
      if (USE_PROXY) {
        // 让OpenRouter模型走代理，解决国内访问问题
        setGlobalDispatcher(PROXY_AGENT);
      }
      setGlobalDispatcher(PROXY_AGENT);
    default:
      return {
        basic: new ChatOpenRouter({
          model: process.env.OPENROUTER_MODEL as string,
          modelKwargs: {
            reasoning: {
              effort: 'none'
            }
          }
        }),
        pro: new ChatOpenRouter({
          model: process.env.OPENROUTER_MODEL_PRO as string,
          modelKwargs: {
            reasoning: {
              effort: 'none'
            }
          }
        })
      };
  }
}

export { llmFactory };
