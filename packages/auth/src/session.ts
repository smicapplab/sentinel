import type { Context, Next } from 'hono';
import { db, sessions, users, stores } from '@sentinel/db';
import { eq, and, gt } from 'drizzle-orm';
import crypto from 'node:crypto';

export interface UserSession {
  userId: string;
  email: string;
  franchiseId: string;
  storeId?: string | null;
  storeNumber?: string | null;
  role: 'super_admin' | 'franchise_admin' | 'store_manager' | 'auditor';
}

declare module 'hono' {
  interface ContextVariableMap {
    session: UserSession;
  }
}

/**
 * Validates session against the local Sentinel database.
 * Sentinel issues its own sessions after validating credentials with araneta-auth.
 * Fail-closed: Any missing or unverified credential returns HTTP 401.
 */
export async function authMiddleware(c: Context, next: Next) {
  const authHeader = c.req.header('Authorization');
  const sessionCookie = c.req.header('Cookie');
  const token = authHeader?.replace(/^Bearer\s+/i, '') || extractCookieToken(sessionCookie);

  if (!token) {
    return c.json({ error: 'Unauthorized: Missing session token' }, 401);
  }

  // Local Dev Bypass: Requires explicit SENTINEL_DEV_SECRET matching in dev mode only
  if (process.env.NODE_ENV === 'development' && process.env.SENTINEL_DEV_SECRET) {
    if (token === process.env.SENTINEL_DEV_SECRET) {
      c.set('session', {
        userId: '00000000-0000-0000-0000-000000000001',
        email: 'dev@araneta.com.ph',
        franchiseId: '00000000-0000-0000-0000-000000000001',
        role: 'franchise_admin',
      });
      return next();
    }
  }

  try {
    const hashedToken = crypto.createHash('sha256').update(token).digest('hex');

    const result = await db
      .select({
        userId: users.id,
        email: users.email,
        franchiseId: users.franchiseId,
        storeId: users.storeId,
        storeNumber: stores.storeNumber,
        role: users.role,
      })
      .from(sessions)
      .innerJoin(users, eq(sessions.userId, users.id))
      .leftJoin(stores, eq(users.storeId, stores.id))
      .where(
        and(
          eq(sessions.id, hashedToken),
          gt(sessions.expiresAt, new Date())
        )
      )
      .limit(1);

    if (!result || result.length === 0) {
      return c.json({ error: 'Unauthorized: Invalid or expired session' }, 401);
    }

    const payload = result[0];
    c.set('session', {
      userId: payload.userId,
      email: payload.email,
      franchiseId: payload.franchiseId,
      storeId: payload.storeId,
      storeNumber: payload.storeNumber,
      role: payload.role as UserSession['role'],
    });

    return next();
  } catch (err) {
    console.error('[sentinel-auth] Local DB session validation failed:', err);
    return c.json({ error: 'Authentication service unavailable' }, 503);
  }
}

function extractCookieToken(cookieHeader?: string): string | null {
  if (!cookieHeader) return null;
  const match = cookieHeader.match(/sentinel_session=([^;]+)/);
  return match ? match[1] : null;
}
