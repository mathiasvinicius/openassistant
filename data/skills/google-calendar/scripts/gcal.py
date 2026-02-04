#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timezone


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_google():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except Exception as e:
        raise RuntimeError(
            "Missing python deps. Run scripts/bootstrap.sh (it installs google-api-python-client, google-auth, google-auth-oauthlib)."
        ) from e
    return Request, Credentials, InstalledAppFlow, build


def _scopes():
    scopes = _env("GCAL_SCOPES", "https://www.googleapis.com/auth/calendar")
    return [s.strip() for s in scopes.split(",") if s.strip()]


def _paths():
    client_secret_path = _env(
        "GCAL_CLIENT_SECRET_PATH",
        "/home/node/.openclaw/credentials/google-calendar/client_secret.json",
    )
    client_id = _env("GCAL_CLIENT_ID")
    client_secret = _env("GCAL_CLIENT_SECRET")
    token_path = _env(
        "GCAL_TOKEN_PATH",
        "/home/node/.openclaw/credentials/google-calendar/token.json",
    )
    calendar_id = _env("GCAL_CALENDAR_ID", "primary")
    # Everything has defaults. We only error later if we need interactive auth
    # and no client config exists (file missing and no env creds).
    return client_secret_path, token_path, calendar_id


def _client_config_from_env():
    client_id = _env("GCAL_CLIENT_ID")
    client_secret = _env("GCAL_CLIENT_SECRET")
    if not (client_id and client_secret):
        return None

    # For a "Web application" OAuth client, the client config lives under "web".
    # We include redirect URIs that match the localserver callback used by the script.
    oauth_host = _env("GCAL_OAUTH_HOST", "localhost") or "localhost"
    oauth_port = int(_env("GCAL_OAUTH_PORT", "8765"))
    redirect_uris = [
        f"http://{oauth_host}:{oauth_port}/",
        f"http://localhost:{oauth_port}/",
        f"http://127.0.0.1:{oauth_port}/",
    ]

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": redirect_uris,
        }
    }


def _ensure_parent(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def load_creds(interactive: bool):
    Request, Credentials, InstalledAppFlow, build = _load_google()
    client_secret_path, token_path, _calendar_id = _paths()
    scopes = _scopes()

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes=scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _ensure_parent(token_path)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return creds

    if not interactive:
        raise RuntimeError("Not authenticated. Run auth first: scripts/auth.sh")

    client_cfg = _client_config_from_env()
    if client_cfg is not None:
        flow = InstalledAppFlow.from_client_config(client_cfg, scopes=scopes)
    else:
        if not os.path.exists(client_secret_path):
            raise RuntimeError(
                "Missing OAuth client config.\n"
                f"- Put the JSON at: {client_secret_path}\n"
                "- OR set env vars: GCAL_CLIENT_ID and GCAL_CLIENT_SECRET\n"
            )
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, scopes=scopes)

    # Auth modes:
    # - localserver: starts a localhost callback server (recommended).
    # - console: tries a copy/paste code flow (may fail if your OAuth client doesn't allow OOB redirect URIs).
    auth_mode = (_env("GCAL_AUTH_MODE", "localserver") or "localserver").strip().lower()
    if auth_mode == "console":
        try:
            # Try OOB/copy-paste style. Many newer Google OAuth clients disallow this;
            # if it fails, we fall back to localserver below.
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            auth_url, _state = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )
            print("Open this URL in your browser:\n")
            print(auth_url)
            print("\nPaste the authorization code here:")
            code = input("code> ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials
        except Exception as e:
            print(
                "Console auth failed (Google may block OOB copy/paste codes for this client). "
                "Falling back to local server auth.\n"
                f"Details: {e}",
                file=sys.stderr,
            )
            auth_mode = "localserver"

    if auth_mode == "localserver":
        oauth_host = _env("GCAL_OAUTH_HOST", "localhost") or "localhost"
        print(f"Starting local OAuth server on {oauth_host}:{_env('GCAL_OAUTH_PORT', '8765')} ...")
        creds = flow.run_local_server(
            # Some Google OAuth setups reject 127.0.0.1 but accept localhost.
            host=oauth_host,
            port=int(_env("GCAL_OAUTH_PORT", "8765")),
            open_browser=False,
            authorization_prompt_message=(
                "Open this URL in your browser:\n{url}\n\n"
                "If you're on SSH, add port-forwarding for the callback port, e.g.:\n"
                "  ssh -L 8765:127.0.0.1:8765 <host>\n"
            ),
            success_message="Google Calendar auth complete. You can close this tab.",
        )

    _ensure_parent(token_path)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return creds


def calendar_service(creds):
    _, _, _, build = _load_google()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def cmd_auth(_args):
    load_creds(interactive=True)
    _client_secret_path, token_path, calendar_id = _paths()
    print("OK")
    print(f"token_path={token_path}")
    print(f"calendar_id={calendar_id}")


def cmd_list(args):
    creds = load_creds(interactive=False)
    svc = calendar_service(creds)
    _client_secret_path, _token_path, calendar_id = _paths()

    now = _iso_now_utc()
    resp = (
        svc.events()
        .list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=args.limit,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = resp.get("items", [])
    out = []
    for ev in items:
        start = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        end = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
        out.append(
            {
                "id": ev.get("id"),
                "summary": ev.get("summary"),
                "start": start,
                "end": end,
                "status": ev.get("status"),
                "htmlLink": ev.get("htmlLink"),
            }
        )

    print(json.dumps({"now": now, "calendarId": calendar_id, "events": out}, ensure_ascii=True, indent=2))


def cmd_add(args):
    creds = load_creds(interactive=False)
    svc = calendar_service(creds)
    _client_secret_path, _token_path, calendar_id = _paths()

    body = {
        "summary": args.summary,
        "start": {"dateTime": args.start},
        "end": {"dateTime": args.end},
    }
    if args.description:
        body["description"] = args.description
    if args.location:
        body["location"] = args.location

    created = svc.events().insert(calendarId=calendar_id, body=body).execute()
    print(json.dumps({"created": {"id": created.get("id"), "htmlLink": created.get("htmlLink")}}, ensure_ascii=True, indent=2))


def main(argv):
    p = argparse.ArgumentParser(prog="gcal")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser("auth", help="OAuth login (local server callback)")
    p_auth.set_defaults(func=cmd_auth)

    p_list = sub.add_parser("list", help="List upcoming events")
    p_list.add_argument("--limit", type=int, default=10)
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Create an event")
    p_add.add_argument("--summary", required=True)
    p_add.add_argument("--start", required=True)
    p_add.add_argument("--end", required=True)
    p_add.add_argument("--description")
    p_add.add_argument("--location")
    p_add.set_defaults(func=cmd_add)

    args = p.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
