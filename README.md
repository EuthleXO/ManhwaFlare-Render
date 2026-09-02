# ManhwaFlare (Render)

Upstream: https://github.com/EuthleXO/ManhwaFlare-Render

Telegram manhwa PDF bot — multi-source, premium, channel privacy.

## Render deploy

1. New → **Web Service** → connect this repo  
2. Build: `pip install -r requirements.txt`  
3. Start: `PYTHONPATH=. python -m Manhwaflare.main`  
4. Health: `/health`  
5. Env vars (required):

| Key | Notes |
|-----|--------|
| `BOT_TOKEN` | @BotFather |
| `OWNER_ID` | your Telegram user id (one owner only) |
| `MONGODB_URI` | **full Atlas URI** — see below |

### MongoDB URI (common crash fix)

Error:
```text
DNS query name does not exist: _mongodb._tcp.cluster.mongodb.net
```

Means the host is a **placeholder**. Fix:

1. [MongoDB Atlas](https://cloud.mongodb.com) → your cluster → **Connect** → **Drivers**
2. Copy URI like:
   `mongodb+srv://user:pass@cluster0.ab12cd.mongodb.net/?retryWrites=true&w=majority`
3. Host must look like `cluster0.**random**.mongodb.net` — **not** `cluster.mongodb.net`
4. Network Access → Allow from anywhere `0.0.0.0/0` (Render has dynamic IPs)

Optional: `OWNER_USERNAME`, `LOG_CHANNEL_ID`, `SUPPORT_CHANNEL`, `SUPPORT_GROUP`

## Local

```bash
pip install -r requirements.txt
export BOT_TOKEN=... OWNER_ID=... MONGODB_URI=...
PYTHONPATH=. python -m Manhwaflare.main
```
