import { Hono } from 'hono';
import { db, users, sessions } from '@sentinel/db';
import { eq } from 'drizzle-orm';
import crypto from 'node:crypto';

export const authRouter = new Hono();

const ARANETA_AUTH_URL = process.env.ARANETA_AUTH_URL || 'http://localhost:5170';

authRouter.post('/login', async (c) => {
  try {
    const body = await c.req.json();
    const { email, password } = body;

    if (!email || !password) {
      return c.json({ error: 'Email and password required' }, 400);
    }

    // 1. Verify user exists in Sentinel and get their role/franchise
    const sentinelUser = await db.query.users.findFirst({
      where: eq(users.email, email),
    });

    if (!sentinelUser || !sentinelUser.isActive) {
      return c.json({ error: 'Unauthorized: User not provisioned in Sentinel' }, 403);
    }

    // 2. Verify credentials against centralized Araneta Auth IdP
    const response = await fetch(`${ARANETA_AUTH_URL}/api/v1/auth/verify-credentials`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      return c.json({ error: 'Invalid email or password' }, 401);
    }
    
    // 3. Credentials are valid. Generate a high-entropy session token.
    const rawToken = crypto.randomBytes(32).toString('hex');
    const hashedToken = crypto.createHash('sha256').update(rawToken).digest('hex');

    // Token expires in 24 hours
    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000);

    // 4. Store ONLY the hash in the database
    await db.insert(sessions).values({
      id: hashedToken,
      userId: sentinelUser.id,
      expiresAt,
    });

    // 5. Return the raw token to the client (via Secure HttpOnly cookie)
    c.header('Set-Cookie', `sentinel_session=${rawToken}; HttpOnly; Path=/; SameSite=Lax; Max-Age=86400`);

    return c.json({
      user: {
        id: sentinelUser.id,
        email: sentinelUser.email,
        role: sentinelUser.role,
        franchiseId: sentinelUser.franchiseId,
      }
    });

  } catch (err) {
    console.error('[sentinel-auth] Login route error:', err);
    return c.json({ error: 'Authentication service unavailable' }, 503);
  }
});
