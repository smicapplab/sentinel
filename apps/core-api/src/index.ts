import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { authMiddleware } from '@sentinel/auth';
import { healthRouter } from './routes/health.js';
import { rollupsRouter } from './routes/rollups.js';
import { anomaliesRouter } from './routes/anomalies.js';

import { authRouter } from './routes/auth.js';

const app = new Hono();

// Global health route (public)
app.route('/api/v1', healthRouter);

// Public auth route (for generating sessions)
app.route('/api/v1/auth', authRouter);

// Protected routes (require franchise authentication)
app.use('/api/v1/*', authMiddleware);
app.route('/api/v1/rollups', rollupsRouter);
app.route('/api/v1/anomalies', anomaliesRouter);

const port = Number(process.env.CORE_API_PORT || 5175);
console.log(`[sentinel-core-api] Starting on port ${port}...`);

serve({
  fetch: app.fetch,
  port,
});
