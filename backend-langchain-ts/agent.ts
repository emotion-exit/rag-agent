import { createAgent } from 'langchain';
import { ChatOpenRouter } from '@langchain/openrouter';
import { MemorySaver } from '@langchain/langgraph';

// tools
import getWeather from './tools/get-weather';
import fetchTextFromUrl from './tools/fetch-text-from-url';

import dotenv from 'dotenv';

dotenv.config();

// model
const model = new ChatOpenRouter({
  model: process.env.LLM_MODEL as string,
  apiKey: process.env.LLM_API_KEY as string
});

// system prompt
const SYSTEM_PROMPT = `你是一个文学数据分析助手。

## 能力
- 必须使用中文回答。
- \`fetch_text_from_url\`：从 URL 加载文档文本到当前对话中。
不要猜测行数或位置——必须基于工具结果中保存的文件内容来得出结论。`;

// memory
const checkpointer = new MemorySaver();

// agent
const agent = createAgent({
  model,
  tools: [fetchTextFromUrl],
  systemPrompt: SYSTEM_PROMPT,
  checkpointer
});

// content
const content = `Project Gutenberg 提供了 F. Scott Fitzgerald 所著《了不起的盖茨比》的完整纯文本版本。
  URL: https://www.gutenberg.org/files/64317/64317-0.txt

  请尽可能回答以下问题：

  1) 在完整的 Gutenberg 文件中，有多少行包含子字符串 \`Gatsby\`（统计“行数”，不是同一行内出现的次数；每一行都以换行符结束）。
  2) 文件中第一行包含 \`Daisy\` 的 1-based 行号是多少。
  3) 用两句话给出一个中性的内容摘要。

  请尽力完成第 (1) 和第 (2) 题。如果你在任何时候意识到自己无法用现有工具和推理**验证**精确答案，请不要编造数字：该字段使用 \`null\`，并在 \`how_you_computed_counts\` 中明确说明限制原因。如果你遇到任何错误，请报告错误类型以及错误信息。`;

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
