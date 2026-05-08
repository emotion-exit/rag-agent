import { tool } from 'langchain';
import * as z from 'zod';

// This tool fetches the text content of a document from a given URL with a timeout and error handling.
export default tool(
  async ({ url }: { url: string }): Promise<string> => {
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      controller.abort();
    }, 120_000); // 120 seconds timeout

    try {
      const response = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; quickstart-research-bot/1.0)'
        },
        signal: controller.signal
      });

      if (!response.ok) {
        return `Failed to fetch the document. HTTP status: ${response.status}`;
      }

      return await response.text();
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      return `Error fetching the document: ${errorMessage}`;
    } finally {
      clearTimeout(timeout);
    }
  },
  {
    name: 'fetch_text_from_url',
    description: 'Fetch the document from a URL',
    schema: z.object({
      url: z.url()
    })
  }
);
