import { tool } from 'langchain';
import * as z from 'zod';

export default tool((input) => `It's always sunny in ${input.city}!`, {
  name: 'get_weather',
  description: 'Get the weather for a given city',
  schema: z.object({
    city: z.string().describe('The name of the city to get the weather for')
  })
});
