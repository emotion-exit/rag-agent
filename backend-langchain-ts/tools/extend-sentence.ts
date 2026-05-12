import { tool, type ToolRuntime } from 'langchain';
import * as z from 'zod';

export default tool(
  (input, config: ToolRuntime) => {
    const writer = config.writer;

    // 流式输出tool的结果
    if (writer) {
      writer(`正在将输入修饰成两条正规的书面表达...\n`);
    }

    return `这是第一条正式表达：${input.sentence1}\n
这是第二条正式表达：${input.sentence2}\n`;
  },
  {
    name: 'extend-sentence',
    description: '将用户的输入扩写成两条书面表达',
    schema: z.object({
      sentence1: z.string().describe('第一条正式表达'),
      sentence2: z.string().describe('第二条正式表达')
    })
  }
);
