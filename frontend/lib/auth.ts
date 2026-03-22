import CredentialsProvider from 'next-auth/providers/credentials';
import type { NextAuthOptions } from 'next-auth';

const API_BASE_URL = process.env.NEXTAUTH_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type AuthRole = 'citizen' | 'county_official' | 'rescue_team';

const AUTH_REQUEST_TIMEOUT_MS = 8000;

interface ProfileResponse {
  ward_name?: string;
  role?: AuthRole;
}

type JwtPayload = {
  exp?: number;
};

function parseJwtExpiryMs(token?: string): number | undefined {
  if (!token) return undefined;
  const parts = token.split('.');
  if (parts.length < 2) return undefined;
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(Buffer.from(padded, 'base64').toString('utf8')) as JwtPayload;
    if (!payload.exp) return undefined;
    return payload.exp * 1000;
  } catch {
    return undefined;
  }
}

async function refreshAccessToken(refreshToken?: string): Promise<{ accessToken?: string; refreshToken?: string; accessTokenExpiresAt?: number }> {
  if (!refreshToken) return {};
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken }),
    });
    if (!response.ok) return {};

    const data = (await response.json()) as { access?: string; refresh?: string };
    const nextAccess = data.access;
    const nextRefresh = data.refresh || refreshToken;
    return {
      accessToken: nextAccess,
      refreshToken: nextRefresh,
      accessTokenExpiresAt: parseJwtExpiryMs(nextAccess),
    };
  } catch {
    return {};
  }
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs = AUTH_REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

export const authOptions: NextAuthOptions = {
  session: { strategy: 'jwt' },
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
        phone: { label: 'Phone', type: 'text' },
        otp: { label: 'OTP', type: 'text' },
      },
      async authorize(credentials) {
        const phone = String(credentials?.phone || '').trim();
        const otp = String(credentials?.otp || '').trim();
        const isPhoneOtpMode = Boolean(phone && otp);

        let response: Response;
        try {
          if (isPhoneOtpMode) {
            response = await fetchWithTimeout(`${API_BASE_URL}/api/alerts/otp/login/`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ phone, otp }),
            });
          } else {
            response = await fetchWithTimeout(`${API_BASE_URL}/api/auth/token/`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                username: credentials?.email,
                password: credentials?.password,
              }),
            });
          }
        } catch {
          return null;
        }

        if (!response.ok) return null;
        const data = await response.json();

        let role: AuthRole = 'citizen';
        let wardName = 'Westlands';
        try {
          const profileRes = await fetchWithTimeout(`${API_BASE_URL}/api/citizens/me/`, {
            headers: { Authorization: `Bearer ${data.access}` },
            cache: 'no-store',
          });
          if (profileRes.ok) {
            const profile = (await profileRes.json()) as ProfileResponse;
            role = profile.role || role;
            wardName = profile.ward_name || wardName;
          }
        } catch {
          // Keep authentication resilient if profile lookup fails.
        }

        return {
          id: isPhoneOtpMode ? phone : credentials?.email || 'user',
          email: credentials?.email || phone,
          accessToken: data.access,
          refreshToken: data.refresh,
          accessTokenExpiresAt: parseJwtExpiryMs(data.access),
          role,
          wardName,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        const tokenUser = user as unknown as {
          accessToken?: string;
          refreshToken?: string;
          accessTokenExpiresAt?: number;
          role?: AuthRole;
          wardName?: string;
        };
        token.accessToken = tokenUser.accessToken;
        token.refreshToken = tokenUser.refreshToken;
        token.accessTokenExpiresAt = tokenUser.accessTokenExpiresAt;
        token.role = tokenUser.role;
        token.wardName = tokenUser.wardName;
      }

      const expiresAt = Number(token.accessTokenExpiresAt || 0);
      const shouldRefresh = Boolean(token.refreshToken) && (!expiresAt || Date.now() >= expiresAt - 30_000);
      if (shouldRefresh) {
        const refreshed = await refreshAccessToken(token.refreshToken as string | undefined);
        if (refreshed.accessToken) {
          token.accessToken = refreshed.accessToken;
          token.refreshToken = refreshed.refreshToken || token.refreshToken;
          token.accessTokenExpiresAt = refreshed.accessTokenExpiresAt;
        }
      }

      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.accessTokenExpiresAt = token.accessTokenExpiresAt as number | undefined;
      session.role = (token.role as AuthRole) || 'citizen';
      session.wardName = (token.wardName as string) || 'Westlands';
      return session;
    },
  },
  pages: {
    signIn: '/signin',
  },
};
