import { Hono } from 'hono';
import { db, discountVoidAnomalies, nbiRecommendations, withFranchiseScope } from '@sentinel/db';
import { requireFranchiseScope } from '@sentinel/auth';
import { desc, eq } from 'drizzle-orm';

export const anomaliesRouter = new Hono();

// Project #7: Discount & Void Fraud Anomaly Radar Leaderboard
anomaliesRouter.get('/fraud-radar', async (c) => {
  const franchiseId = requireFranchiseScope(c);
  const session = c.get('session');
  let branch = c.req.query('branch');

  if (session.role === 'store_manager') {
    if (!session.storeNumber) {
      return c.json({ error: 'Forbidden: Store Manager lacks store assignment' }, 403);
    }
    branch = session.storeNumber;
  }

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

  const isPrivileged = ['auditor', 'loss_prevention', 'admin', 'super_admin', 'franchise_admin'].includes(session.role);

  const redactedResults = results.map(row => ({
    ...row,
    cashierName: isPrivileged ? row.cashierName : (row.cashierName ? 'Cashier ****' : null)
  }));

  return c.json({ data: redactedResults });
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
