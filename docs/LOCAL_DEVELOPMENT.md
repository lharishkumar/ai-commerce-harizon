# Local development guide

This guide runs the store locally with Docker Compose, Auth0 login, synthetic product/order data, mock payments, and the LiveKit voice agent. It is intended for development and end-to-end testing, not production deployment.

## 1. What you need

- Windows 10/11 with Docker Desktop installed and running (Linux containers enabled).
- Git and a current browser such as Chrome or Edge.
- The existing Auth0 tenant/client from the prior project. The local `.env` was populated with that tenant and client.
- Internet access for Docker images and the configured Auth0, LiveKit Cloud, Deepgram, and OpenAI services.

Docker Desktop supplies the local PostgreSQL database. You do not need to install PostgreSQL separately for this path.

## 2. Allow the new local callback in Auth0

The Auth0 client was reused from the prior project. In its Auth0 application settings, add these exact values (keep any existing entries):

- Allowed Callback URLs: `http://localhost:8000/api/auth/callback`
- Allowed Web Origins: `http://localhost:3000`
- Allowed Logout URLs: `http://localhost:3000`

Enable the Auth0 connections you want shoppers to use (for example Google, Microsoft, or another SSO provider). Auth0 Universal Login lets those providers authenticate without asking this store for a separate password. Each connection must return a verified email. The backend maps the login to the Auth0 identity subject and refuses unverified emails. It does not merge accounts just because two providers report the same email; use Auth0's verified account-linking flow if you need one customer/order history shared across providers. Never paste the client secret into frontend code or commit `.env`.

## 3. Start the application

Open PowerShell in the project folder:

```powershell
cd D:\AI\Langraph_Class\stock-analyzer-web\ai-voice-commerce
docker compose config --quiet
docker compose up --build
```

The first build downloads images and dependencies and may take several minutes. Keep this terminal open. When the `web`, `api`, and `db` services are healthy/running, open:

- Storefront: `http://localhost:3000`
- API health: `http://localhost:8000/api/health`
- API reference: `http://localhost:8000/docs`

If `docker compose config` reports an interpolation/configuration problem, verify `.env` exists in this project folder beside `compose.yaml`. Do not post its contents in chat or commit it.

## 4. Try the end-to-end store journey

1. Search or filter the synthetic electronics catalog; open a product to inspect details/specifications.
2. Add products to the bag and proceed to checkout.
3. Sign in. The browser should redirect to Auth0 and return to the storefront. If Auth0 reports a callback URL error, complete step 2 and retry.
4. Complete checkout. `PAYMENT_PROVIDER=mock` is intentional for local testing; the UI simulates a successful payment through a development-only API route. No real payment is taken.
5. Open the account/order view to check the order created for the signed-in customer.
6. Open HarizonAI and use **Live voice with HarizonAI**. Allow microphone access, then ask about a product or policy as a guest. For order questions, sign in and reconnect voice; provide an order reference or date when asked. Typed chat is also available.
7. Try the human-support action. Review/confirm the ticket prompt; the app should return a ticket reference.

## 5. What the environment currently configures

The new `.env` is ignored by Git. It contains:

- Auth0 tenant/client settings reused from the prior project, with the new local callback URL.
- A newly generated session-signing secret (it is not shared with the prior project).
- The prior OpenAI API key/model, Deepgram key, and LiveKit Cloud URL/key/secret. The worker registered with LiveKit; a complete browser voice call is still needed to confirm Deepgram/OpenAI credentials and audio end to end.
- Development mode, local PostgreSQL URL, mock payment mode, and LiveKit UI mode.
- Empty Razorpay test credentials. No Cartesia key is needed: this agent uses OpenAI TTS for spoken output.

Do not share `.env` or copy its secret values into screenshots, source code, tickets, or Git. `.env.example` is the safe template. If the previous OpenAI key should not be shared across projects, replace `OPENAI_API_KEY` with a dedicated development key or leave it blank; catalog/policy checkout should still be exercised without the LiveKit voice-agent profile.

## 6. LiveKit voice setup and verification

The local `.env` is set to `VOICE_MODE=livekit` and `NEXT_PUBLIC_LIVEKIT_MODE=livekit`. The agent uses Deepgram Flux for streaming speech recognition, OpenAI for its response and speech synthesis, and LiveKit Cloud for the audio session. OpenAI's LiveKit plugin supports the configured `gpt-4o-mini-tts` model and uses `OPENAI_API_KEY` for authentication ([LiveKit OpenAI TTS guide](https://docs.livekit.io/agents/models/tts/openai/)).

1. Confirm `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, and `OPENAI_API_KEY` are populated in `.env`. Do not print or send their values.
2. From the project root run `docker compose config --quiet`.
3. Start/rebuild the app and voice worker: `docker compose --profile voice up -d --build`.
4. Check `docker compose --profile voice ps`; `db`, `api`, `web`, and `voice-agent` should be running.
5. Check `docker compose --profile voice logs --tail 100 voice-agent` for worker startup errors. Do not share logs without checking for secrets.
6. Open the storefront, sign in, open HarizonAI, click **Start live voice**, allow microphone access, and ask a product/policy question. During its reply, click **Stop reply** to interrupt speech while keeping the call connected; use **End voice** to disconnect. Test order lookup while signed in.

The LiveKit key and endpoint must belong to the same LiveKit Cloud project.
### Follow the voice flow as a developer

In a second PowerShell window, follow the worker log while making a voice call:

```powershell
docker compose --profile voice logs -f voice-agent
```

Expected entries show `session.connecting`, `session.connected`, `session.ready`, `agent.state`, `turn.transcribed`, and `tool.started`/`tool.completed`. A catalog question should call `search_catalog`; a delivery/returns/warranty question should call `explain_policy`; an order question should call `lookup_order_details`. Guests can use public store information; order lookup requires a verified sign-in. If the session started before login, reconnect voice to refresh its short-lived customer authorization. An authenticated order request can use an order reference or date; if it matches multiple owned orders, HarizonAI asks which one. Clicking **Stop reply** logs `voice.stop_requested` and then `voice.reply_stopped` (or `voice.stop_no_active_reply` if it was already quiet); **End voice** disconnects and logs `session.closed`. `turn.transcription_timeout` means the worker detected speech but Deepgram did not return a transcript in time. `tool.failed` includes only the exception class for API troubleshooting, not exception text that might include a user query.

These application logs intentionally omit spoken transcript text, product search text, customer identity, and raw audio. For a tool error, also inspect the API log with `docker compose --profile voice logs --tail 100 api`. The LiveKit worker startup line confirms it connected to LiveKit, but only a browser microphone call confirms the full Deepgram → OpenAI → speech playback path. LiveKit Agent Insights may retain transcripts/recordings according to LiveKit project settings; keep those settings aligned with the project's no-transcript-by-default goal. The worker has registered successfully, but provider keys being present in `.env` does not prove they are valid or have billing/quota enabled. Complete a browser microphone call to validate the full path. OpenAI is used for both LLM and TTS; Cartesia is not required. Provider pricing and speech latency depend on your accounts and network.

## 7. Rebuild and run after code or configuration changes

From the project root, after editing frontend/backend/voice-agent code, Docker files, or `.env`, run:

```powershell
docker compose --profile voice up -d --build --force-recreate
docker compose --profile voice ps
```

The `NEXT_PUBLIC_*` values are compiled into the storefront, so changes to those values require the rebuild. Then reload `http://localhost:3000`; if the page appears stale, use `Ctrl+F5`. Inspect service logs with `docker compose --profile voice logs --tail 100 web api voice-agent`.

For backend tests after API changes:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_store_flow.py -q
cd ..
```

For frontend compile/type checks after UI changes, run `npm.cmd run build` from `frontend`.

## 8. Switch from mock payments to Razorpay test mode

Only do this after the mock journey works. Add Razorpay **test-mode** values for `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET`, then set `PAYMENT_PROVIDER=razorpay` and rebuild/restart. Configure the provider webhook to reach `/api/payments/razorpay/webhook` through a local webhook tunnel if needed. Never use live keys for local development. Razorpay's test checkout requires its provider dashboard and webhook setup; it is not configured yet.

## 9. Run the automated backend tests

In a second PowerShell window:

```powershell
cd D:\AI\Langraph_Class\stock-analyzer-web\ai-voice-commerce\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest tests\test_store_flow.py -q
```

If PowerShell blocks activation, skip activation and use the virtual-environment executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests\test_store_flow.py -q
```

## 10. Stop and restart

- Stop foreground services with `Ctrl+C`.
- Restart later with `docker compose --profile voice up -d`.
- Stop containers and keep the database volume with `docker compose --profile voice down`.
- `docker compose down -v` also deletes the local database and all locally created orders/tickets; only use it when you intentionally want a fresh database.

## Architecture in brief

- `frontend/`: Next.js storefront and assistant panel.
- `backend/app/`: FastAPI APIs, customer session checks, catalog, order lifecycle, payment adapter, and support tickets.
- `backend/migrations/`: database schema migrations.
- `voice-agent/`: optional LiveKit worker with speech and LLM provider adapters.
- `compose.yaml`: local PostgreSQL, API, web, and optional voice services.

The local database is the development order source. Production order/payment authority, security hardening, deployment, backup/retention policy, and concurrency targets still require separate validation before launch.

