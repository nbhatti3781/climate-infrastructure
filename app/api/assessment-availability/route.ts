import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { NextResponse } from "next/server";

export async function GET() {
  const root = path.join(process.cwd(), "data", "processed");
  const indexPath = path.join(root, "assessment-publications.json");
  const index = fs.existsSync(indexPath) ? JSON.parse(fs.readFileSync(indexPath, "utf8")) : {};
  const published: string[] = [];
  for (const [key, entry] of Object.entries(index)) {
    const match = /^(current|202[1-5]):(flood|wildfire):(10001|10003|10005)$/.exec(key);
    const item = entry as { validation_status?: string; sha256?: string;
      methodology_status?: string; source_validation_status?: string; observation_year?: number };
    if (!match || item.validation_status !== "validated") continue;
    const [, period, hazard, geoid] = match;
    if (period !== "current" && (item.methodology_status !== "approved" ||
      item.source_validation_status !== "validated" || item.observation_year !== Number(period))) continue;
    const file = path.join(root, "assessments", period, hazard, "counties", `${geoid}.json`);
    if (fs.existsSync(file) && createHash("sha256").update(fs.readFileSync(file)).digest("hex") === item.sha256) published.push(key);
  }
  return NextResponse.json({ published }, { headers: { "Cache-Control": "no-store" } });
}
