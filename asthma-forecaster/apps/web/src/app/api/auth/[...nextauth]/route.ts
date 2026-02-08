import NextAuth, { NextAuthOptions } from "next-auth"
import GoogleProvider from "next-auth/providers/google"
import { userExistsByEmail } from "@/lib/users"

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  callbacks: {
    redirect: async ({ url, baseUrl }) => {
      // After sign-in, never send users back to the sign-in page; use home instead
      const signInPath = "/auth/signin"
      if (url.startsWith(signInPath) || url === `${baseUrl}${signInPath}`) {
        return `${baseUrl}/breathe-well`
      }
      if (url.startsWith("/")) return `${baseUrl}${url}`
      if (new URL(url).origin === baseUrl) return url
      return `${baseUrl}/breathe-well`
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub || ""
        session.needsRegistration = token.needsRegistration ?? false
      }
      return session
    },
    async jwt({ token, account, profile, user }) {
      if (account) {
        token.accessToken = account.access_token
        token.id = profile?.sub ?? user?.sub
      }
      // On first sign-in (user present), check if email is registered in backend
      if (user?.email) {
        try {
          const exists = await userExistsByEmail(user.email)
          token.needsRegistration = !exists
        } catch {
          token.needsRegistration = true
        }
      }
      return token
    },
  },
  pages: {
    signIn: '/auth/signin',
    error: '/auth/error',
  },
  session: {
    strategy: "jwt",
  },
}

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }
