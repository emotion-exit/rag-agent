import { createAgent, createMiddleware } from 'langchain';
import { MemorySaver } from '@langchain/langgraph';

// factory
import { llmFactory } from './factory';

// tools
import extendSentence from './tools/extend-sentence';

// model
const { basic, pro } = llmFactory();

// system prompt
const SYSTEM_PROMPT = `
你是一个语句修饰专家，能够将用户输入的句子扩写成两条正规的书面表达。
通过调用工具extend-sentence来完成这个任务。
要求：
1. 你只能使用工具extend-sentence来修饰用户输入的句子，不能直接输出修饰后的句子。
2. 必须使用中文，必须使用markdown格式。
3. 你应该默认用户输入的句子是非正式的口语表达，你的任务是将它们修饰成正式的书面表达。
4. 除非用户明确让你不要扩写或者修饰，你在做其他回答。
`;

// memory
const checkpointer = new MemorySaver();

// middleware
console.log('Basic model:', basic.model);
console.log('Pro model:', pro.model);
console.log(
  'Use pro model firstly, and switch to basic model after 2 rounds of conversation'
);
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
  tools: [extendSentence],
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
