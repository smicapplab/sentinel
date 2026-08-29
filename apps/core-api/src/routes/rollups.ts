import { Hono } from 'hono';
import { db, posDailyStoreSales, posHourlySalesSummary, withFranchiseScope } from '@sentinel/db';
import { requireFranchiseScope } from '@sentinel/auth';
import { eq, desc } from 'drizzle-orm';

export const rollupsRouter = new Hono();

// Get daily store sales rollups scoped strictly by franchise
rollupsRouter.get('/daily-sales', async (c) => {
  const franchiseId = requireFranchiseScope(c);
  const session = c.get('session');
  let branch = c.req.query('branch');

  if (session.role === 'store_manager') {
    if (!session.storeNumber) {
      return c.json({ error: 'Forbidden: Store Manager lacks store assignment' }, 403);
    }
    branch = session.storeNumber;
  }

  let whereClause = withFranchiseScope(posDailyStoreSales.franchiseId, franchiseId);
  if (branch) {
    whereClause = withFranchiseScope(posDailyStoreSales.franchiseId, franchiseId, eq(posDailyStoreSales.branch, branch));
  }

  const results = await db
    .select()
    .from(posDailyStoreSales)
    .where(whereClause)
    .orderBy(desc(posDailyStoreSales.repdate))
    .limit(100);

  return c.json({ data: results });
});

// Get hourly daypart sales summaries
rollupsRouter.get('/hourly-summary', async (c) => {
  const franchiseId = requireFranchiseScope(c);
  const session = c.get('session');
  let branch = c.req.query('branch');

  if (session.role === 'store_manager') {
    if (!session.storeNumber) {
      return c.json({ error: 'Forbidden: Store Manager lacks store assignment' }, 403);
    }
    branch = session.storeNumber;
  }

  let whereClause = withFranchiseScope(posHourlySalesSummary.franchiseId, franchiseId);
  if (branch) {
    whereClause = withFranchiseScope(posHourlySalesSummary.franchiseId, franchiseId, eq(posHourlySalesSummary.branch, branch));
  }

  const results = await db
    .select()
    .from(posHourlySalesSummary)
    .where(whereClause)
    .orderBy(desc(posHourlySalesSummary.repdate))
    .limit(100);

  return c.json({ data: results });
});
