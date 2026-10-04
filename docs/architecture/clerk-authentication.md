# Clerk Authentication & Google SSO Architecture

## 1. Overview & Objectives

PracPrep supports hybrid authentication:
1. **Native PracPrep Authentication**: Email/password authentication issuing HS256 JWT access and refresh tokens.
2. **Clerk Authentication with Google SSO**: OAuth 2.0 social sign-in powered by Clerk React SDK on the frontend, verified against Clerk's JWKS via RS256 public-key cryptography on the FastAPI backend, and synchronized into PracPrep's local database.
3. **Guest Mode & Data Migration**: Full preservation of guest lab experiments and study notes in `localStorage`, offering seamless migration to the newly authenticated Clerk/Google account.

This architecture ensures:
- **Zero UI Disruption**: Brand styling, layout, typography, and theme tokens are preserved identically.
- **Zero Database Schema Migrations**: Clerk users map to existing `User` and `UserSettings` records with `auth_provider="clerk:<clerk_user_id>"`.
- **Zero Incompatible API Changes**: After authentication via Clerk, PracPrep issues standard native access/refresh tokens, keeping all downstream API routes (`/labs/*`, `/users/*`, `/study/*`) completely agnostic to the auth method.

---

## 2. Environment Configuration

### Frontend (`.env.local`)
Create or edit `.env.local` in the project root:
```env
# Clerk Publishable Key (from Clerk Dashboard -> API Keys)
VITE_CLERK_PUBLISHABLE_KEY=pk_test_ZWxlZ2FudC1yaGluby04MDcxLmNsZXJrLmFjY291bnRzLmRldiQ
```

> **Security Note**: Never commit `.env.local` to version control. Ensure it is listed in `.gitignore`.

### Backend (`backend/.env`)
Add Clerk configuration variables to `backend/.env`:
```env
# Clerk Publishable Key (used to automatically infer frontend API domain and JWKS URL)
CLERK_PUBLISHABLE_KEY=pk_test_ZWxlZ2FudC1yaGluby04MDcxLmNsZXJrLmFjY291bnRzLmRldiQ

# Optional: Clerk Secret Key for backend operations
CLERK_SECRET_KEY=sk_test_...

# Optional: Explicit issuer and JWKS URL overrides (automatically inferred if omitted)
# CLERK_ISSUER="https://elegant-rhino-8071.clerk.accounts.dev"
# CLERK_JWKS_URL="https://elegant-rhino-8071.clerk.accounts.dev/.well-known/jwks.json"
```

The backend automatically extracts the Clerk frontend API domain by decoding the base64 prefix of the publishable key:
`pk_test_<base64_domain>$` -> `<instance>.clerk.accounts.dev`.

---

## 3. Clerk Dashboard & Google OAuth Setup

To enable Google sign-in for PracPrep in the Clerk Dashboard:

1. **Create or Open Application**:
   - Navigate to [dashboard.clerk.com](https://dashboard.clerk.com).
   - Select your PracPrep application (e.g. `elegant-rhino-8071`).
2. **Enable Google Social Connection**:
   - In the sidebar, navigate to **User & Authentication > Social Connections**.
   - Enable **Google**.
   - For development, Clerk provides pre-configured shared credentials ("Use Clerk shared credentials") out of the box.
   - For production, create OAuth 2.0 Client Credentials in the Google Cloud Console and paste the Client ID and Client Secret into Clerk.
3. **Configure Redirect URLs**:
   - In **Paths / Redirects**, verify the allowed redirect URIs include:
     - Development: `http://localhost:5173/sso-callback`
     - Production: `https://<your-domain>/sso-callback`
4. **Copy API Keys**:
   - Navigate to **API Keys** and copy the **Publishable Key**. Paste into `.env.local` as `VITE_CLERK_PUBLISHABLE_KEY`.

---

## 4. Architecture & Token Exchange Flow

### End-to-End Sequence Diagram

```
User               Frontend (PracPrep)            Clerk Hosted / Google         Backend (FastAPI)
 │                          │                               │                         │
 ├─ Click "Google SSO" ────►│                               │                         │
 │                          ├─ signIn.authenticateWith... ─►│                         │
 │                          │  (redirects to Google)        │                         │
 │                          │                               ├─ User consents          │
 │                          │◄── Redirect to /sso-callback ─┤                         │
 │                          │                               │                         │
 │                          ├─ <AuthenticateWithRedirectCallback />                   │
 │                          ├─ Obtain Clerk session token   │                         │
 │                          │                               │                         │
 │                          ├─ POST /api/v1/auth/clerk-sync ─────────────────────────►│
 │                          │  { clerk_token, email, name } │                         ├─ Fetch RS256 JWKS
 │                          │                               │                         ├─ Verify signature & exp
 │                          │                               │                         ├─ Find or provision User
 │                          │                               │                         ├─ Provision UserSettings
 │                          │◄─ Return native JWT tokens (access + refresh) ──────────┤
 │                          │                               │                         │
 │                          ├─ Store native tokens in tokenManager                    │
 │                          ├─ Check for guest lab items    │                         │
 │                          │   ├─ If guest data: Route to /login?migrate=true        │
 │                          │   └─ Else: Route to /dashboard                          │
 │◄─ Dashboard displayed ───┤                               │                         │
```

---

## 5. Frontend Implementation Details

### Core Modules & Responsibilities

1. **`src/lib/clerk.ts`**:
   - Reads `import.meta.env.VITE_CLERK_PUBLISHABLE_KEY`.
   - Provides validation helpers `getClerkPublishableKey()`, `isClerkConfigured()`, and `getClerkConfigurationError()`.
2. **`src/App.tsx`**:
   - Wraps the application tree in `<ClerkProvider publishableKey={publishableKey}>`.
   - If the key is missing or invalid, gracefully renders a helpful configuration screen without crashing.
   - Mounts `<ClerkSessionBridge />` and the dedicated `/sso-callback` route.
3. **`src/pages/AuthPage.tsx`**:
   - Replaced placeholder alert dialogs with functional Clerk OAuth redirect handlers.
   - Uses `signIn.authenticateWithRedirect({ strategy: 'oauth_google', redirectUrl: '/sso-callback', redirectUrlComplete: '/dashboard' })` for login and signup tabs.
   - Displays loading spinners on the Google button during redirect initialization.
   - Renders contextual error banners if Clerk or network errors occur.
4. **`src/pages/SSOCallbackPage.tsx`**:
   - Renders Clerk's `<AuthenticateWithRedirectCallback />` to finalize OAuth token exchange.
   - Retrieves the verified session token using `session.getToken()`.
   - Calls `authService.syncClerkSession(token, userEmail, fullName)`.
   - Inspects `localStorage` for `pracprep_guest_labs` or `guest_study_notes`. If guest data is present, redirects to `/login?migrate=true`; otherwise redirects directly to `/dashboard`.
5. **`src/components/auth/ClerkSessionBridge.tsx`**:
   - Monitors `useSession()` and `useUser()` from Clerk.
   - If an active Clerk session is detected but native tokens are missing from `tokenManager`, triggers background sync to maintain authentication continuity.
6. **`src/services/authService.ts`**:
   - Implements `syncClerkSession(clerkToken, email, name)`.
   - Dispatches `POST /api/v1/auth/clerk-sync`.
   - Updates `tokenManager` and `localStorage` session state.
   - Emits session change notifications.

---

## 6. Backend Implementation Details

### Core Modules & Verification

1. **`backend/app/core/clerk.py` (`ClerkTokenVerifier`)**:
   - Initializes `jwt.PyJWKClient(jwks_url, ssl_context=...)`.
   - Configures an SSL context with `certifi.where()` to guarantee valid CA root bundle resolution across macOS, Linux, and Docker environments.
   - Enforces the `RS256` algorithm explicitly (rejects `none`, `HS256`, etc.).
   - Verifies token signature, issuer, expiration, and extracts the subject claim (`sub`).
2. **`backend/app/modules/auth/router.py` (`POST /api/v1/auth/clerk-sync`)**:
   - Rate-limited endpoint using slowapi (`"10/minute"`).
   - Validates the incoming Clerk RS256 token against Clerk's JWKS.
   - Normalizes email address (lowercase, trimmed).
   - Queries database for existing `User` record:
     - **If user exists**: Verifies account is active (`is_active=True`). Links account provider if unset.
     - **If user does not exist**: Atomically provisions a new `User` record with `auth_provider="clerk:<sub">`, `email_verified=True`, a secure dummy password hash (disallowing password login unless reset), and creates a corresponding `UserSettings` record.
   - Generates and returns native PracPrep HS256 `access_token` and `refresh_token`.
3. **`backend/app/modules/auth/dependencies.py` (`get_current_user`)**:
   - **Dual-Token Support**:
     1. First attempts decoding the token with PracPrep native `HS256` secret.
     2. If native decoding fails, falls back to `ClerkTokenVerifier.verify_clerk_token(token)`.
     3. Resolves the user from the database by email or subject claim.
     4. Unhandled database exceptions propagate cleanly as 500 errors without mask.

---

## 7. Guest Mode & Data Migration Contract

PracPrep supports an unauthenticated "Guest Mode" where users explore virtual labs and generate notes stored locally in browser storage:
- `pracprep_guest_labs`: Array of guest experiments and progress.
- `pracprep_guest_notes`: Notes created during guest sessions.

### Migration Flow with Clerk SSO
1. When a guest starts an experiment, items are written to `localStorage`.
2. The user decides to sign in or sign up via "Continue with Google".
3. The user completes the Google authentication on Clerk.
4. `/sso-callback` detects the active session and checks `localStorage.getItem('pracprep_guest_labs')`.
5. If guest items exist:
   - User is routed to `/login?migrate=true`.
   - The `GuestMigrationModal` automatically opens with native PracPrep tokens now active.
   - The user clicks "Transfer My Work".
   - `migrationService.migrateGuestData()` submits data to `POST /api/v1/labs/migrate-guest`.
   - Guest items in `localStorage` are cleared, and the user continues with preserved history.
6. If no guest items exist, the user routes directly to `/dashboard`.

---

## 8. Verification & Test Coverage

### Automated Backend Tests (`backend/tests/test_clerk_auth.py`)
- `test_clerk_verifier_raises_when_no_jwks_url`: Validates clean failure when unconfigured.
- `test_clerk_verifier_success`: Verifies valid RS256 RSA key signature validation and claims extraction.
- `test_clerk_verifier_expired_token`: Verifies rejection of expired tokens.
- `test_clerk_verifier_tampered_key`: Verifies rejection when signature does not match JWKS public key.
- `test_clerk_verifier_wrong_algorithm`: Verifies rejection of algorithm spoofing (e.g. HS256).
- `test_clerk_sync_endpoint_new_user`: Tests atomic user creation and `UserSettings` creation.
- `test_clerk_sync_endpoint_existing_user`: Tests existing user linking and token generation.
- `test_clerk_sync_endpoint_inactive_user`: Verifies 403 Forbidden on inactive user.
- `test_clerk_sync_endpoint_missing_token`: Verifies 400 Bad Request on invalid payloads.
- `test_get_current_user_clerk_fallback`: Verifies fallback authentication on standard endpoints.
- `test_get_current_user_native_jwt_non_regression`: Guarantees native JWT authentication is unimpacted.

### Automated Frontend Tests (`test-clerkAuth.mjs`)
- `test-1-clerk-configuration`: Asserts publishable key structure and validation functions.
- `test-2-auth-service-sync`: Asserts `syncClerkSession` dispatches correct payload and updates session.
- `test-3-auth-service-sync-error`: Asserts network/API error propagation without crashing.
- `test-4-guest-data-preservation`: Asserts guest lab storage is preserved across SSO callbacks.
- `test-5-logout-cleans-native-and-clerk-tokens`: Asserts clean token purging on logout.
- `test-6-native-login-regression`: Guarantees standard email/password authentication remains intact.

### Running the Test Suites
```bash
# Frontend test suite (12 test suites, 120+ tests)
npm test

# Frontend type checking and build
npm run build

# Backend test suite (781 tests)
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_*.py
```

---

## 9. Troubleshooting & FAQ

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `Clerk Publishable Key is missing or invalid` banner | `VITE_CLERK_PUBLISHABLE_KEY` is empty or malformed | Ensure `.env.local` contains `VITE_CLERK_PUBLISHABLE_KEY=pk_test_...` and restart Vite dev server (`npm run dev`). |
| SSL: `CERTIFICATE_VERIFY_FAILED` on backend | Python environment lacks default CA certificates | `ClerkTokenVerifier` uses `certifi.where()` automatically. Ensure `certifi` is installed in `backend/requirements.txt`. |
| "Google SSO Integration placeholder" alert appears | Outdated or unbuilt frontend bundle | Ensure `src/pages/AuthPage.tsx` changes are loaded. Clear browser cache and reload. |
| Account inactive error (403) | `User.is_active` set to `False` in PracPrep database | Re-activate user record via admin interface or database console. |
| Guest data lost after Google login | Guest data was in a different browser profile or private window | Ensure the user returns to the same browser session or completes migration via `/login?migrate=true`. |
