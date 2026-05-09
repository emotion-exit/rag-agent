import { createAgent } from 'langchain';
import { MemorySaver } from '@langchain/langgraph';

// factory
import { llmFactory } from './factory';

// model
const model = llmFactory('ollama');

// system prompt
const SYSTEM_PROMPT = `你是一个有用的助手，专门用来分析文本内容并回答用户的问题。你可以使用工具来获取文本内容并进行分析。请根据用户提供的内容和问题，尽力给出准确的答案。`;

// memory
const checkpointer = new MemorySaver();

// agent
const agent = createAgent({
  model,
  systemPrompt: SYSTEM_PROMPT,
  checkpointer
});

// content
const content = `解释一下RAG是什么？`;

// invoke agent
async function chat() {
  const agentResult = await agent.invoke(
    {
      messages: [
        {
          role: 'user',
          content
        }
      ]
    },
    {
      configurable: {
        thread_id: 'great-gatsby-lc'
      }
    }
  );
  const agentMessages = agentResult.messages;
  return agentMessages[agentMessages.length - 1]!.contentBlocks;
}

export { chat };
