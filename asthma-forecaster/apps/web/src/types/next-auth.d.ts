import NextAuth, { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    user: {
      id: string
    } & DefaultSession["user"]
    needsRegistration?: boolean
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: string
    accessToken?: string
    needsRegistration?: boolean
  }
}

declare module "next-auth/react" {
  export function signIn(
    provider?: string,
    options?: { callbackUrl?: string; redirect?: boolean }
  ): Promise<void>
  export function signOut(options?: { callbackUrl?: string }): Promise<void>
  export function useSession(): {
    data: import("next-auth").Session | null
    status: "loading" | "authenticated" | "unauthenticated"
  }
  export const SessionProvider: (props: {
    children: React.ReactNode
    session?: import("next-auth").Session | null
  }) => React.ReactElement
}
