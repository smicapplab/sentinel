import { Hono } from 'hono';
import { db, tlogrcp, posDeadLetters } from '@sentinel/db';
import crypto from 'node:crypto';

export const ingestRouter = new Hono();

if (!process.env.POS_API_KEY_PH) {
  throw new Error('CRITICAL: POS_API_KEY_PH environment variable is missing.');
}

// Franchise API key mapping (In production, stored hashed in DB / AWS Secrets Manager)
const POS_KEY_STORE: Record<string, string> = {
  // franchiseId -> expected key
  '00000000-0000-0000-0000-000000000001': process.env.POS_API_KEY_PH,
};

function authenticatePosKey(apiKey: string): string | null {
  for (const [franchiseId, expectedKey] of Object.entries(POS_KEY_STORE)) {
    if (apiKey.length === expectedKey.length && crypto.timingSafeEqual(Buffer.from(apiKey), Buffer.from(expectedKey))) {
      return franchiseId;
    }
  }
  return null;
}

// High-throughput POS batch webhook receiver
ingestRouter.post('/transactions', async (c) => {
  const apiKey = c.req.header('X-POS-API-KEY');
  if (!apiKey) {
    return c.json({ error: 'Unauthorized: Missing X-POS-API-KEY' }, 401);
  }

  // Validate key and resolve authenticated franchise
  const authenticatedFranchiseId = authenticatePosKey(apiKey);
  if (!authenticatedFranchiseId) {
    return c.json({ error: 'Unauthorized: Invalid POS API key' }, 401);
  }

  const payload = await c.req.json();
  const items = Array.isArray(payload) ? payload : [payload];

  if (items.length === 0) {
    return c.json({ status: 'ignored', count: 0 });
  }

  // Invariant: Override any client-supplied franchiseId with authenticatedFranchiseId
  const sanitizedRows = items.map((item: any) => ({
    franchiseId: authenticatedFranchiseId,
    repdate: item.repdate,
    branch: item.branch,
    transact: String(item.transact),
    lineid: Number(item.lineid) || 1,
    trandesc: item.trandesc ? String(item.trandesc) : null,
    voidFlg: item.voidFlg === 'Y' ? 'Y' : 'N',
    trandate: item.trandate,
    trantime: item.trantime,
    receipt: item.receipt,
    cashierId: item.cashierId ? String(item.cashierId) : null,
    cashierName: item.cashierName ? String(item.cashierName) : null,
    rowtype: item.rowtype ? String(item.rowtype) : 'ITEM',
    prodcode: item.prodcode ? String(item.prodcode) : null,
    proddesc: item.proddesc ? String(item.proddesc) : null,
    prodprice: item.prodprice ? String(item.prodprice) : null,
    amount: String(item.amount || '0'),
    diners: item.diners ? Number(item.diners) : null,
    scguestcnt: item.scguestcnt ? Number(item.scguestcnt) : null,
    rsontype: item.rsontype ? String(item.rsontype) : null,
    apprvlCode: item.apprvlCode ? String(item.apprvlCode) : null,
  }));

  // Batch insert into TLOGRCP stream with chunking and partial success
  const CHUNK_SIZE = 100;
  let successCount = 0;

  for (let i = 0; i < sanitizedRows.length; i += CHUNK_SIZE) {
    const chunk = sanitizedRows.slice(i, i + CHUNK_SIZE);
    try {
      await db.insert(tlogrcp).values(chunk).onConflictDoNothing();
      successCount += chunk.length;
    } catch (err: any) {
      await db.insert(posDeadLetters).values({
        franchiseId: authenticatedFranchiseId,
        payload: chunk,
        errorReason: err.message || 'Unknown constraint violation',
      });
    }
  }

  return c.json({
    status: 'accepted',
    count: successCount,
    franchiseId: authenticatedFranchiseId,
    timestamp: new Date().toISOString(),
  });
});
