import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { ingestRouter } from './routes/ingest.js';

const app = new Hono();

app.get('/health', (c) => c.json({ status: 'ok', service: 'sentinel-pos-api', uptime: process.uptime() }));
app.route('/api/v1/ingest', ingestRouter);

const port = Number(process.env.POS_API_PORT || 5176);
console.log(`[sentinel-pos-api] Starting on port ${port}...`);

serve({
  fetch: app.fetch,
  port,
});
