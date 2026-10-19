# U.S. Climate Infrastructure Dashboard

An interactive county-level dashboard for transportation exposure to climate hazards across the United States.

## Current status

- Nationwide state and county selection using U.S. Census TIGERweb boundaries
- Four hazard views: inland flood, wildfire, hurricane inundation, and drought–heavy rain
- Validated inland-flood calculation for Howard County, Maryland
- Maryland wildfire view using USDA Forest Service WHP 2023 and FEMA NRI wildfire annual probability; Howard County validated first
- Compact precomputed county results designed to avoid large downloads in the browser

Assessment results are currently available for Maryland only; nationwide map
navigation does not imply nationwide computed results. The dashboard's
“Available assessment” label lists WHP 2023 and HPMS 2024, and flags unrecorded
FEMA NRI/NFHL and TIGERweb release vintages. These are baseline assessments,
not dashboard year options.

Saved historical audit progress and the checkpoint/validation requirements for
future nationwide processing are in
[Nationwide pipeline readiness](docs/nationwide-pipeline-readiness.md).

The validated transportation-stress framework is:

`normalized hazard frequency × exposed-road share × normalized traffic consequence`

## Run locally

Requires Node.js 22 or newer and pnpm.

```bash
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

## Production build

```bash
pnpm build
pnpm start
```

## Data pipeline

Python preprocessing code is in `pipeline/`. It retrieves official GIS data, performs spatial calculations outside the browser, and writes compact county JSON outputs for the dashboard.

See `pipeline/README.md` for methodology and commands.

Wildfire processing is limited to Maryland's 23 counties and Baltimore city.
Exposure measures major-road length in **High / Very High** wildfire hazard
potential cells, not all land where wildfire can occur. Final wildfire stress
is 0 for confirmed zero exposure with a major-road network. For positive exposure it
remains pending the national wildfire-specific exposed-road traffic percentile;
Maryland ranks are not substituted. Flood outputs are stored separately and
remain unchanged.

## Deployment

This repository is a standard Next.js project and can be imported directly into Vercel. The frontend is public and does not depend on ChatGPT authentication or ChatGPT Sites.
