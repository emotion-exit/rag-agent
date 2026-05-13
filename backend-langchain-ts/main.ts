import './utils/logger';
import { chat } from './agent';
import Fastify from 'fastify';
import cors from '@fastify/cors';

const fastify = Fastify({
  logger: true
});

fastify.register(cors, {
  origin: '*',
  methods: ['GET', 'POST', 'OPTIONS']
});

fastify.post('/chat', async (request, reply) => {
  const message = await (request.body as { message: string }).message;

  reply.hijack();
  reply.raw.writeHead(200, {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no'
  });
  try {
    for await (const chunk of chat(message)) {
      reply.raw.write(JSON.stringify(chunk) + '\n');
    }
    reply.raw.write(JSON.stringify({ type: 'done' }) + '\n');
  } catch (error) {
    console.error('Error in /chat handler:', error);
    const errorMessage = error instanceof Error ? error.message : String(error);
    reply.raw.write(
      JSON.stringify({ type: 'error', message: errorMessage, error }) + '\n'
    );
  } finally {
    reply.raw.end();
  }
});

fastify.listen({ port: 3000 }, (err, address) => {
  if (err) throw err;
  // Server is now listening on ${address}
});
