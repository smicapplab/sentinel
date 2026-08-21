import type { Context, Next } from 'hono';

export function requireRole(allowedRoles: string[]) {
  return async (c: Context, next: Next) => {
    const session = c.get('session');
    if (!session || !allowedRoles.includes(session.role)) {
      return c.json({ error: 'Forbidden: Insufficient privileges' }, 403);
    }
    return next();
  };
}

export function requireFranchiseScope(c: Context): string {
  const session = c.get('session');
  if (!session?.franchiseId) {
    throw new Error('Security violation: Request lacks franchise_id scope');
  }
  return session.franchiseId;
}
