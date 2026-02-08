import { getDb, USERS_COLLECTION } from "./db"

export interface UserProfile {
  name?: string
  height?: string
  weight?: string
  gender?: string
}

export interface StoredUser {
  _id?: string
  email: string
  name?: string
  profile?: UserProfile
  createdAt: Date
  updatedAt: Date
}

export async function userExistsByEmail(email: string): Promise<boolean> {
  if (!email) return false
  const db = await getDb()
  const user = await db.collection(USERS_COLLECTION).findOne({ email })
  return !!user
}

export async function createOrUpdateUser(
  email: string,
  data: Partial<StoredUser> & { profile?: UserProfile }
): Promise<void> {
  if (!email) return
  const db = await getDb()
  const now = new Date()
  const { profile, ...rest } = data
  await db.collection(USERS_COLLECTION).updateOne(
    { email },
    {
      $set: {
        ...rest,
        ...(profile && { profile }),
        email,
        updatedAt: now,
      },
      $setOnInsert: {
        createdAt: now,
      },
    },
    { upsert: true }
  )
}

export async function getUserByEmail(email: string): Promise<StoredUser | null> {
  if (!email) return null
  const db = await getDb()
  const doc = await db.collection(USERS_COLLECTION).findOne({ email })
  if (!doc) return null
  return {
    _id: String(doc._id),
    email: doc.email,
    name: doc.name,
    profile: doc.profile,
    createdAt: doc.createdAt,
    updatedAt: doc.updatedAt,
  }
}
