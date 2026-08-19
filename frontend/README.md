# TRADEVERSE frontend

Next.js 15 app deployed on **Vercel**. Connects to the cloud API worker via `NEXT_PUBLIC_API_URL`.

## Local dev

```bash
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Requires the API worker running locally — see [../DEPLOYMENT.md](../DEPLOYMENT.md).

## Vercel deploy

1. Root directory: `frontend/`
2. Set `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, `NEXT_PUBLIC_API_PREFIX`
3. Deploy

See [../DEPLOYMENT.md](../DEPLOYMENT.md) for full setup.
