import { Hono } from 'hono';
import { db, discountVoidAnomalies, nbiRecommendations, withFranchiseScope } from '@sentinel/db';
import { requireFranchiseScope } from '@sentinel/auth';
import { desc, eq } from 'drizzle-orm';

export const anomaliesRouter = new Hono();

// Project #7: Discount & Void Fraud Anomaly Radar Leaderboard
anomaliesRouter.get('/fraud-radar', async (c) => {
  const franchiseId = requireFranchiseScope(c);
  const branch = c.req.query('branch');

  let whereClause = withFranchiseScope(discountVoidAnomalies.franchiseId, franchiseId);
  if (branch) {
    whereClause = withFranchiseScope(discountVoidAnomalies.franchiseId, franchiseId, eq(discountVoidAnomalies.branch, branch));
  }

  const results = await db
    .select()
    .from(discountVoidAnomalies)
    .where(whereClause)
    .orderBy(desc(discountVoidAnomalies.zScore))
    .limit(50);

  return c.json({ data: results });
});

// Project #4: Next-Best-Item (NBI) Recommendation Pairings
anomaliesRouter.get('/nbi-recommendations', async (c) => {
  const franchiseId = requireFranchiseScope(c);
  const channel = c.req.query('channel');

  let whereClause = withFranchiseScope(nbiRecommendations.franchiseId, franchiseId);
  if (channel) {
    whereClause = withFranchiseScope(nbiRecommendations.franchiseId, franchiseId, eq(nbiRecommendations.channel, channel));
  }

  const results = await db
    .select()
    .from(nbiRecommendations)
    .where(whereClause)
    .orderBy(desc(nbiRecommendations.incrementalMarginPeso))
    .limit(50);

  return c.json({ data: results });
});
