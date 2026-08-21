import { Hono } from 'hono';

export const healthRouter = new Hono();

healthRouter.get('/health', (c) => {
  return c.json({
    status: 'ok',
    service: 'sentinel-core-api',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  });
});
