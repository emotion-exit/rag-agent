import { createAgent, createMiddleware } from 'langchain';
import { MemorySaver } from '@langchain/langgraph';

// factory
import { llmFactory } from './factory';

// model
const { basic, pro } = llmFactory('ollama');

// system prompt
const SYSTEM_PROMPT = `你是一个有用的助手，专门用来分析文本内容并回答用户的问题。你可以使用工具来获取文本内容并进行分析。请根据用户提供的内容和问题，尽力给出准确的答案。`;

// memory
const checkpointer = new MemorySaver();

// middleware
const midlleware = createMiddleware({
  name: 'dynamic-llm-middleware',
  wrapModelCall(request, handler) {
    const messageCount = request.messages.length;
    // 切换模型，如果连问超过两轮，就切换到basic模型，否则使用pro模型
    if (messageCount < 2) {
      request.model = pro;
    } else {
      request.model = basic;
    }
    return handler(request);
  }
});

// agent
const agent = createAgent({
  model: pro,
  systemPrompt: SYSTEM_PROMPT,
  checkpointer,
  middleware: [midlleware]
});

// invoke agent by streaming
async function* chat(userPrompt: string) {
  const stream = await agent.stream(
    {
      messages: [
        {
          role: 'user',
          content: userPrompt
        }
      ]
    },
    {
      streamMode: 'messages',
      configurable: {
        thread_id: 'great-gatsby-lc'
      }
    }
  );

  for await (const [token, metadata] of stream) {
    yield {
      type: 'token',
      text: token,
      metadata
    };
  }
}

export { chat };
