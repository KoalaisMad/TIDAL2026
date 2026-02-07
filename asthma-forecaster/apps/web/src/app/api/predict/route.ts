import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json(); // { userId, date }
  const r = await fetch(`${process.env.ML_SERVICE_URL}/predict`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await r.json();
  return NextResponse.json(data);
}
