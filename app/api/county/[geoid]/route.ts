import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ geoid: string }> }
) {
  const { geoid } = await params;

  // Validate: must be 5-digit FIPS
  if (!/^\d{5}$/.test(geoid)) {
    return NextResponse.json({ error: "Invalid GEOID" }, { status: 400 });
  }

  const filePath = path.join(
    process.cwd(),
    "data",
    "processed",
    "counties",
    `${geoid}.json`
  );

  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
  return NextResponse.json(data);
}
