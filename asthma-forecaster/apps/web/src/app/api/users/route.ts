import clientPromise from "@/lib/mongodb";
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json(); // { lat, lon, timezone }
  const client = await clientPromise;
  const db = client.db("asthma");

  const result = await db.collection("users").insertOne({
    home: { lat: body.lat, lon: body.lon },
    timezone: body.timezone ?? "UTC",
    createdAt: new Date()
  });

  return NextResponse.json({ userId: result.insertedId.toString() });
}
