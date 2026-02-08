import { getDb, USERS_COLLECTION } from "./db"

/** Stored in user.checkIns[] in MongoDB. Short daily check-in (10–15 sec). */
export interface DailyCheckInRecord {
  date: string // ISO date YYYY-MM-DD
  wheeze: number // ordinal 0–3
  cough: number // ordinal 0–3
  chestTightness: number // ordinal 0–3
  exerciseMinutes: number // minutes
}

/** Stored in user.profile in MongoDB. Used for BMI (height, weight) and risk. */
export interface UserProfile {
  name?: string
  height?: string // for BMI
  weight?: string // for BMI
  gender?: string
  smokerStatus?: string
  petExposure?: string
  bmi?: number // computed from height/weight
}

export interface StoredUser {
  _id?: string
  email: string
  name?: string
  profile?: UserProfile
  checkIns?: DailyCheckInRecord[]
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
    checkIns: doc.checkIns,
    createdAt: doc.createdAt,
    updatedAt: doc.updatedAt,
  }
}

export async function addCheckIn(
  email: string,
  checkIn: DailyCheckInRecord
): Promise<void> {
  if (!email) return
  const db = await getDb()
  const now = new Date()
  await db.collection(USERS_COLLECTION).updateOne(
    { email },
    {
      $set: { updatedAt: now },
      $push: { checkIns: checkIn },
    }
  )
}

/** All users with a valid email (for daily morning notifications). */
export async function getAllUsersWithEmail(): Promise<
  Array<{ email: string; name?: string }>
> {
  const db = await getDb()
  const cursor = db
    .collection(USERS_COLLECTION)
    .find({ email: { $exists: true, $ne: "" } })
    .project({ email: 1, name: 1 })
  const docs = await cursor.toArray()
  return docs.map((d) => ({
    email: String(d.email ?? ""),
    name: d.name != null ? String(d.name) : undefined,
  }))
}
