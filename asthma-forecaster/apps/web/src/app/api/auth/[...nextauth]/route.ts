import NextAuth, { NextAuthOptions } from "next-auth"
import GoogleProvider from "next-auth/providers/google"

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  callbacks: {
    async session({ session, token }) {
      // Add user id to the session
      if (session.user) {
        session.user.id = token.sub || ""
      }
      return session
    },
    async jwt({ token, account, profile }) {
      // Persist additional data to the token
      if (account) {
        token.accessToken = account.access_token
        token.id = profile?.sub
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
