# Google OAuth 2.0 Setup Guide

This guide will help you set up Google OAuth 2.0 for your Asthma Monitor application.

## 1. Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API:
   - Go to **APIs & Services** > **Library**
   - Search for "Google+ API"
   - Click **Enable**

4. Create OAuth 2.0 credentials:
   - Go to **APIs & Services** > **Credentials**
   - Click **Create Credentials** > **OAuth client ID**
   - Choose **Web application**
   - Add authorized redirect URIs:
     - Development: `http://localhost:3000/api/auth/callback/google`
     - Production: `https://yourdomain.com/api/auth/callback/google`
   - Click **Create**
   - Copy the **Client ID** and **Client Secret**

## 2. Configure Environment Variables

Update your `.env.local` file with the credentials:

```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=<generate-a-random-secret>
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
```

### Generate NEXTAUTH_SECRET

Run this command to generate a secure secret:
```bash
openssl rand -base64 32
```

Or use Node.js:
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

## 3. NextAuth Endpoints

The following endpoints are automatically created:

- **Sign In**: `http://localhost:3000/auth/signin`
- **Sign Out**: `http://localhost:3000/api/auth/signout`
- **Session**: `http://localhost:3000/api/auth/session`
- **Providers**: `http://localhost:3000/api/auth/providers`
- **CSRF Token**: `http://localhost:3000/api/auth/csrf`

## 4. Using Authentication in Your App

### Client Components

```tsx
"use client"
import { useSession, signIn, signOut } from "next-auth/react"

export default function Component() {
  const { data: session, status } = useSession()
  
  if (status === "loading") {
    return <div>Loading...</div>
  }
  
  if (session) {
    return (
      <>
        <p>Signed in as {session.user?.email}</p>
        <button onClick={() => signOut()}>Sign out</button>
      </>
    )
  }
  
  return (
    <>
      <p>Not signed in</p>
      <button onClick={() => signIn("google")}>Sign in with Google</button>
    </>
  )
}
```

### Server Components

```tsx
import { getSession, getCurrentUser } from "@/lib/auth"

export default async function ServerComponent() {
  const session = await getSession()
  const user = await getCurrentUser()
  
  if (!session) {
    return <p>Please sign in</p>
  }
  
  return <p>Welcome {user?.name}</p>
}
```

### API Routes

```tsx
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"

export async function GET() {
  const session = await getServerSession(authOptions)
  
  if (!session) {
    return new Response("Unauthorized", { status: 401 })
  }
  
  return Response.json({ data: "Protected data" })
}
```

## 5. Protecting Routes

### Middleware Approach (Optional)

Create `middleware.ts` in the root:

```tsx
export { default } from "next-auth/middleware"

export const config = {
  matcher: ["/asthma-monitor/:path*", "/dashboard/:path*"]
}
```

### Component Approach

```tsx
"use client"
import { useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { useEffect } from "react"

export default function ProtectedPage() {
  const { data: session, status } = useSession()
  const router = useRouter()
  
  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/auth/signin")
    }
  }, [status, router])
  
  if (status === "loading") {
    return <div>Loading...</div>
  }
  
  return <div>Protected content</div>
}
```

## 6. Testing

1. Start your development server:
   ```bash
   npm run dev
   ```

2. Visit: `http://localhost:3000/auth/signin`

3. Click "Continue with Google"

4. Complete the Google sign-in flow

5. You should be redirected back to your application

## 7. Session Management

NextAuth uses JWT tokens by default. Sessions are stored in HTTP-only cookies and are automatically refreshed.

### Session Configuration

- **Strategy**: JWT (stateless, no database required)
- **Max Age**: 30 days (default)
- **Update Age**: 24 hours (default)

### Accessing Session Data

The session object contains:
```tsx
{
  user: {
    id: string
    name: string
    email: string
    image: string
  },
  expires: string
}
```

## 8. Troubleshooting

### Error: "redirect_uri_mismatch"
- Ensure the redirect URI in Google Console matches exactly: `http://localhost:3000/api/auth/callback/google`

### Error: "invalid_client"
- Check that your Client ID and Client Secret are correct in `.env.local`

### Session not persisting
- Ensure `NEXTAUTH_URL` matches your current domain
- Check that cookies are enabled in your browser

## 9. Production Deployment

1. Update `NEXTAUTH_URL` to your production domain
2. Add production redirect URI to Google Console
3. Generate a new `NEXTAUTH_SECRET` for production
4. Never commit `.env.local` to version control
5. Set environment variables in your hosting platform

## Additional Resources

- [NextAuth.js Documentation](https://next-auth.js.org/)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [NextAuth.js Examples](https://next-auth.js.org/getting-started/example)
