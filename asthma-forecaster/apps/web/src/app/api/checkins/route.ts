import clientPromise from "@/lib/mongodb";
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json();
  const client = await clientPromise;
  const db = client.db("asthma");

  const result = await db.collection("checkins").updateOne(
    { userId: body.userId },
    {
      $set: { ...body, updatedAt: new Date() },
      $setOnInsert: { createdAt: new Date() },
    },
    { upsert: true }
  );

  return NextResponse.json({
    acknowledged: result.acknowledged,
    upsertedId: result.upsertedId?.toString(),
  });
}
