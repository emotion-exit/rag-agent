import { createAgent, createMiddleware } from 'langchain';
import { MemorySaver } from '@langchain/langgraph';

// factory
import { llmFactory } from './factory';

// model
const { basic, pro } = llmFactory('ollama');

// system prompt
const SYSTEM_PROMPT = `
你是一个有用的助手，请根据用户提供的内容和问题，尽力给出准确的答案。
你需要遵守以下规则：
1. 使用中文回答问题。
2. 使用丰富的markdown格式来组织你的回答，包括标题、列表、代码块等，以提高可读性。
3. 如果用户的问题涉及到代码，请提供示例代码，并用markdown的代码块格式进行展示。
4. 如果你不确定答案，可以说“我不确定，但我会尽力帮助你找到答案”。
`;

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
