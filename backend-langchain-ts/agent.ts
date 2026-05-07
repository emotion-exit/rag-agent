import { createAgent, tool } from 'langchain';
import { ChatOpenRouter } from '@langchain/openrouter';
import * as z from 'zod';
import dotenv from 'dotenv';

dotenv.config();

// tool
const getWeather = tool((input) => `It's always sunny in ${input.city}!`, {
  name: 'get_weather',
  description: 'Get the weather for a given city',
  schema: z.object({
    city: z.string().describe('The name of the city to get the weather for')
  })
});

// model
const model = new ChatOpenRouter({
  model: process.env.LLM_MODEL as string,
  apiKey: process.env.LLM_API_KEY as string
});

// agent
const agent = createAgent({
  model,
  tools: [getWeather]
});

console.log(
  await agent.invoke({
    messages: [{ role: 'user', content: '解释一下RAG是什么' }]
  })
);
