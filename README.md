# U.S. Climate Infrastructure Dashboard

An interactive county-level dashboard for transportation exposure to climate hazards across the United States.

## Current status

- Nationwide state and county selection using U.S. Census TIGERweb boundaries
- Four hazard views: inland flood, wildfire, hurricane inundation, and drought–heavy rain
- Validated inland-flood calculation for Howard County, Maryland
- Compact precomputed county results designed to avoid large downloads in the browser

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

## Deployment

This repository is a standard Next.js project and can be imported directly into Vercel. The frontend is public and does not depend on ChatGPT authentication or ChatGPT Sites.
