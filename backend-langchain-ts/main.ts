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

fastify.get('/chat', async (request, reply) => {
  try {
    const result = await chat();
    reply.code(200);
    return result;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    reply.code(500).send({
      error: 'An error occurred while processing the chat request.',
      details: errorMessage
    });
  }
});

fastify.listen({ port: 3000 }, (err, address) => {
  if (err) throw err;
  // Server is now listening on ${address}
});
