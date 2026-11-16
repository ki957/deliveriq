# Fresh machine to first demo

1. Install Git, Docker Engine with Compose v2, Node 26, npm, OpenSSL, and an editor. Keep at least 2 GiB RAM available. Choose unused API and Postgres host ports (defaults: 8000 and 5433).
2. Clone the repository and enter it:

   ```sh
   git clone https://github.com/ki957/deliveriq.git
   cd deliveriq
   cp .env.example .env
   $EDITOR .env
   ```

   Generate local-only credentials directly into the copied file (the command prints no credential values):

   ```sh
   for key in POSTGRES_SUPERUSER_PASSWORD APP_MIGRATOR_PASSWORD APP_API_PASSWORD WORKER_PASSWORD P1_SOP_PASSWORD P2_ELT_PASSWORD P3_SYNTH_PASSWORD RAG_CUSTOMER_PASSWORD RAG_KITCHEN_PASSWORD RAG_MANAGEMENT_PASSWORD OTP_PEPPER PSEUDONYM_KEY; do
     value=$(openssl rand -hex 32)
     sed -i "s|^${key}=.*|${key}=${value}|" .env
     unset value
   done
   ```

   Keep `APP_ENV=local` and `OTP_ADAPTER=mock`. Set `COMPOSE_PROJECT_NAME` to a unique local name and `API_HOST_PORT` / `POSTGRES_HOST_PORT` to free ports. If `API_HOST_PORT` differs from 8000, use that same port for `VITE_API_PROXY` in step 4. Never paste `.env` contents into logs or support messages.
3. Start the API and database, then the worker and demo data:

   ```sh
   make up
   make worker
   make fixtures
   ```

4. In another terminal install and serve the frontend:

   ```sh
   cd frontend
   npm ci
   VITE_API_PROXY=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1
   ```

   Wait for Vite to print its ready URL, then open `http://127.0.0.1:5173`. Use the mock OTP sign-in with one of these seeded accounts:

   | Role | Mobile |
   |---|---|
   | Customer | `+910000000001` |
   | Delivery Agent | `+910000000002` |
   | Kitchen Staff | `+910000000003` |
   | Kitchen Manager | `+910000000004` |
   | Regional Manager | `+910000000005` |
   | Central Administrator | `+910000000006` |

   The local mock adapter uses its fixed test OTP `123456`; no SMS is sent.
5. Stop the frontend with `Ctrl-C`, then stop the worker and stack:

   ```sh
   make worker-down
   make down
   ```

`make down` preserves the database volume. Keep `.env` locally for the next start.
