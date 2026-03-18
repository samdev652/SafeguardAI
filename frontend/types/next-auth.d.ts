import 'next-auth';

type SessionRole = 'citizen' | 'county_official' | 'rescue_team';

declare module 'next-auth' {
  interface User {
    accessToken?: string;
    refreshToken?: string;
    role?: SessionRole;
    wardName?: string;
  }

  interface Session {
    accessToken?: string;
    role?: SessionRole;
    wardName?: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    role?: SessionRole;
    wardName?: string;
  }
}
