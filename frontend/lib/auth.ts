import CredentialsProvider from 'next-auth/providers/credentials';
import type { NextAuthOptions } from 'next-auth';

const API_BASE_URL = process.env.NEXTAUTH_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type AuthRole = 'citizen' | 'county_official' | 'rescue_team';

const AUTH_REQUEST_TIMEOUT_MS = 8000;

interface ProfileResponse {
  ward_name?: string;
  role?: AuthRole;
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
      },
      async authorize(credentials) {
        let response: Response;
        try {
          response = await fetchWithTimeout(`${API_BASE_URL}/api/auth/token/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: credentials?.email,
              password: credentials?.password,
            }),
          });
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
          id: credentials?.email || 'user',
          email: credentials?.email,
          accessToken: data.access,
          refreshToken: data.refresh,
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
          role?: AuthRole;
          wardName?: string;
        };
        token.accessToken = tokenUser.accessToken;
        token.refreshToken = tokenUser.refreshToken;
        token.role = tokenUser.role;
        token.wardName = tokenUser.wardName;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.role = (token.role as AuthRole) || 'citizen';
      session.wardName = (token.wardName as string) || 'Westlands';
      return session;
    },
  },
  pages: {
    signIn: '/signin',
  },
};
