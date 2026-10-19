import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ geoid: string }> }
) {
  const { geoid } = await params;

  // Validate: must be 5-digit FIPS
  if (!/^\d{5}$/.test(geoid)) {
    return NextResponse.json({ error: "Invalid GEOID" }, { status: 400 });
  }

  const query = new URL(req.url).searchParams;
  const hazard = query.get("hazard") ?? "flood";
  const period = query.get("year") ?? "current";
  if (period !== "current" && !/^202[1-5]$/.test(period)) {
    return NextResponse.json({ error: "Unsupported assessment period" }, { status: 400 });
  }
  if (hazard !== "flood" && hazard !== "wildfire") {
    return NextResponse.json({ error: "Unsupported hazard" }, { status: 400 });
  }
  let filePath = path.join(
    process.cwd(),
    "data",
    "processed",
    ...(hazard === "wildfire" ? ["wildfire"] : []),
    "counties",
    `${geoid}.json`
  );

  // Annual and Delaware results require an explicitly validated publication.
  // Benchmark/staging directories are never served implicitly, even if present.
  if (period !== "current" || !geoid.startsWith("24")) {
    const indexPath = path.join(process.cwd(), "data", "processed", "assessment-publications.json");
    const index = fs.existsSync(indexPath) ? JSON.parse(fs.readFileSync(indexPath, "utf8")) : {};
    const entry = index[`${period}:${hazard}:${geoid}`];
    const annualReady = period === "current" || (entry?.methodology_status === "approved" &&
      entry?.source_validation_status === "validated" && entry?.observation_year === Number(period));
    if (!entry || !annualReady || entry.validation_status !== "validated" || !/^[a-f0-9]{64}$/.test(entry.sha256 ?? "")) {
      return NextResponse.json({
        error: period === "current" ? "No validated published assessment for this county" :
          `No validated annual ${hazard} assessment for ${period}. Current baseline values are not annual observations.`,
        status: "unavailable", assessment_period: period,
      }, { status: 404 });
    }
    filePath = path.join(process.cwd(), "data", "processed", "assessments", period, hazard, "counties", `${geoid}.json`);
    if (!fs.existsSync(filePath)) return NextResponse.json({ error: "Published file missing" }, { status: 503 });
    const { createHash } = await import("node:crypto");
    if (createHash("sha256").update(fs.readFileSync(filePath)).digest("hex") !== entry.sha256) {
      return NextResponse.json({ error: "Published assessment integrity check failed" }, { status: 503 });
    }
  }

  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
  return NextResponse.json(data, { headers: {
    "X-Assessment-Period": period,
    "Cache-Control": "no-store",
    ...(query.get("download") === "1" ? {
      "Content-Disposition": `attachment; filename="${geoid}-${hazard}-${period}.json"`,
    } : {}),
  } });
}
