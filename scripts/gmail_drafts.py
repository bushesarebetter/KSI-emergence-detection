"""Create the outreach emails as Gmail DRAFTS under a label. This script never sends.

What it does
------------
Reads the ten emails in docs/OUTREACH.md, fills in the placeholders you supply,
creates a Gmail label, and saves each email as a draft carrying that label.
Recipients are left BLANK on purpose: you add the real person's address once you
have found them, which also means no draft can be sent by accident.

What it cannot do
-----------------
Gmail has no "drafts only" permission. The narrowest scope that allows creating a
draft (`gmail.compose`) technically also allows sending. The guarantee that nothing
is sent therefore lives in this file, not in the scope: the only Gmail calls made
are labels.list / labels.create / drafts.list / drafts.get / drafts.create. There
is no call to `send` anywhere. Revoke the token afterwards if you like:
https://myaccount.google.com/permissions

One-time setup (about five minutes)
-----------------------------------
1. Same Google Cloud project you already use for the Maps key:
   APIs & Services -> Library -> enable "Gmail API".
2. APIs & Services -> OAuth consent screen -> External -> add your own Gmail
   address under "Test users". (The app stays in testing mode; nothing is
   published.)
3. APIs & Services -> Credentials -> Create credentials -> OAuth client ID ->
   Application type "Desktop app". Download the JSON and save it as:
       data/raw/gmail/credentials.json
   That folder is gitignored. Never commit it.
4. pip install google-auth-oauthlib google-api-python-client

Usage
-----
    # See exactly what would be created, touching nothing:
    python scripts/gmail_drafts.py --dry-run

    # Create the drafts:
    python scripts/gmail_drafts.py --name "Your Name" --school "Your School" --grade 12th-grade

A browser window opens once for consent. Re-running is safe: drafts whose subject
already exists are skipped, so you will not get duplicates.
"""
from __future__ import annotations

import argparse
import base64
import re
import sys
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTREACH = ROOT / "docs" / "OUTREACH.md"
GMAIL_DIR = ROOT / "data" / "raw" / "gmail"          # gitignored via data/raw/**
CREDENTIALS = GMAIL_DIR / "credentials.json"
TOKEN = GMAIL_DIR / "token.json"

# gmail.compose is the narrowest scope that permits drafts.create. See the module
# docstring for why that is not the same as "cannot send".
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
]

DEFAULT_LABEL = "KSI Outreach"
DEFAULT_URL = "https://ksi-emergence-detection.onrender.com"

# Filled from CLI args. [Name] and [SPECIFIC PAPER] are intentionally NOT here:
# they are recipient-specific and you fill them in per draft.
FILLABLE = ("[YOUR NAME]", "[SCHOOL]", "[GRADE]", "[DASHBOARD URL]")


# ── parsing ─────────────────────────────────────────────────────────────────────

def parse_outreach(text: str) -> list[dict]:
    """Extract the numbered emails from OUTREACH.md.

    Each email is a `## N. Institution` heading followed by a blockquote whose
    first line is `> **Subject:** ...`. Parsing the doc rather than duplicating
    the text here keeps a single source of truth: edit the markdown, re-run.
    """
    parts = re.split(r"^## (\d+)\. (.+)$", text, flags=re.M)
    emails = []
    for i in range(1, len(parts), 3):
        number, institution, section = parts[i], parts[i + 1].strip(), parts[i + 2]

        quoted = []
        for line in section.splitlines():
            if line.startswith("> "):
                quoted.append(line[2:])
            elif line.strip() == ">":
                quoted.append("")

        subject, body_lines = None, []
        for line in quoted:
            m = re.match(r"\*\*Subject:\*\*\s*(.+)", line)
            if m and subject is None:
                subject = m.group(1).strip()
            else:
                body_lines.append(line)

        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()

        body = "\n".join(body_lines).replace("&nbsp;", " ")
        emails.append({
            "n": int(number),
            "institution": institution,
            "subject": subject,
            "body": body,
        })
    return emails


def fill(text: str, subs: dict[str, str | None]) -> str:
    for placeholder, value in subs.items():
        if value:
            text = text.replace(placeholder, value)
    return text


# A short "Label:" prefix marks a line that must stay on its own (link lists).
# ...but only when the value is a URL or a bracketed placeholder. Prose after a
# colon ("The question: can you predict...") is a sentence and must flow.
_LABEL_LINE = re.compile(r"^[A-Z][\w -]{0,32}:\s*(https?://\S+|\[[A-Z][A-Z ]*\])\s*$")


def _join_wrapped(lines: list[str]) -> str:
    """Join hard-wrapped lines with spaces -- except after a line that ends in a
    hyphen, where the wrap fell inside a word: "killed-or-" + "serious-injury"
    must come back as "killed-or-serious-injury", not "killed-or- serious-injury"."""
    out = ""
    for line in lines:
        if not out:
            out = line
        elif out.endswith("-"):
            out += line
        else:
            out += " " + line
    return out


def flow_paragraphs(body: str) -> str:
    """Join OUTREACH.md's 80-column hard wraps into flowing paragraphs.

    The markdown is wrapped for readability in git; an email should reflow to the
    reader's screen instead, and most recipients will read it on a phone. Blank
    lines still separate paragraphs. Two things are kept on their own lines: the
    final sign-off paragraph ("Thank you,\\n[YOUR NAME]") and any "Label: value"
    line such as "Map: <url>", so link lists do not collapse into one line.
    """
    paras = re.split(r"\n\s*\n", body.strip())
    out = []
    for i, para in enumerate(paras):
        lines = [l.strip() for l in para.split("\n") if l.strip()]
        if i == len(paras) - 1 or all(_LABEL_LINE.match(l) for l in lines):
            out.append("\n".join(lines))
            continue
        joined, buf = [], []
        for l in lines:
            if _LABEL_LINE.match(l):
                if buf:
                    joined.append(_join_wrapped(buf))
                    buf = []
                joined.append(l)
            else:
                buf.append(l)
        if buf:
            joined.append(_join_wrapped(buf))
        out.append("\n".join(joined))
    return "\n\n".join(out)


def unfilled(text: str) -> list[str]:
    return [p for p in FILLABLE if p in text]


# ── gmail ───────────────────────────────────────────────────────────────────────

def gmail_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit(
            "Missing Google client libraries. Run:\n"
            "  pip install google-auth-oauthlib google-api-python-client"
        )

    if not CREDENTIALS.exists():
        sys.exit(
            f"No OAuth client file at {CREDENTIALS.relative_to(ROOT)}.\n"
            "Follow the one-time setup in the docstring at the top of this script."
        )

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def ensure_label(svc, name: str) -> tuple[str, bool]:
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"].casefold() == name.casefold():
            return label["id"], False
    created = svc.users().labels().create(
        userId="me",
        body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    return created["id"], True


def existing_draft_subjects(svc) -> set[str]:
    """Subjects of every current draft, so re-running never duplicates."""
    subjects, page = set(), None
    while True:
        resp = svc.users().drafts().list(userId="me", maxResults=100, pageToken=page).execute()
        for d in resp.get("drafts", []):
            got = svc.users().drafts().get(userId="me", id=d["id"], format="metadata").execute()
            for h in got.get("message", {}).get("payload", {}).get("headers", []):
                if h.get("name", "").casefold() == "subject":
                    subjects.add(h.get("value", "").strip())
        page = resp.get("nextPageToken")
        if not page:
            break
    return subjects


def create_draft(svc, subject: str, body: str, label_id: str) -> dict:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    # No "To" header, deliberately. Add the recipient in Gmail once you have a
    # named person; an addressless draft cannot be sent even by accident.
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return svc.users().drafts().create(
        userId="me", body={"message": {"raw": raw, "labelIds": [label_id]}}
    ).execute()


# ── main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--name", help="replaces [YOUR NAME]")
    ap.add_argument("--school", help="replaces [SCHOOL]")
    ap.add_argument("--grade", help="replaces [GRADE]; it reads as 'a [GRADE] student', so pass '12th-grade' or 'senior', not '12'")
    ap.add_argument("--dashboard-url", default=DEFAULT_URL, help="replaces [DASHBOARD URL]")
    ap.add_argument("--label", default=DEFAULT_LABEL, help=f"Gmail label (default: {DEFAULT_LABEL!r})")
    ap.add_argument("--dry-run", action="store_true", help="print the drafts; do not touch Gmail")
    args = ap.parse_args()

    if not OUTREACH.exists():
        sys.exit(f"Cannot find {OUTREACH.relative_to(ROOT)}")

    subs = {
        "[YOUR NAME]": args.name,
        "[SCHOOL]": args.school,
        "[GRADE]": args.grade,
        "[DASHBOARD URL]": args.dashboard_url,
    }

    emails = parse_outreach(OUTREACH.read_text(encoding="utf-8"))
    if len(emails) != 10:
        print(f"warning: expected 10 emails in OUTREACH.md, found {len(emails)}")

    prepared = []
    for e in emails:
        subject = fill(e["subject"] or "", subs)
        body = flow_paragraphs(fill(e["body"], subs))
        prepared.append({**e, "subject": subject, "body": body,
                         "unfilled": unfilled(subject + "\n" + body)})

    # ── dry run: show everything, touch nothing ────────────────────────────────
    if args.dry_run:
        for e in prepared:
            print("=" * 78)
            print(f"[{e['n']:2d}] {e['institution']}")
            print(f"     Subject: {e['subject']}")
            if e["unfilled"]:
                print(f"     UNFILLED: {', '.join(e['unfilled'])}")
            print("-" * 78)
            print(e["body"])
            print()
        print(f"{len(prepared)} drafts would be created under label {args.label!r}. "
              "Nothing was written to Gmail (--dry-run).")
        return

    still = sorted({p for e in prepared for p in e["unfilled"]})
    if still:
        print(f"note: these placeholders are still unfilled and will appear in the "
              f"drafts as-is: {', '.join(still)}")
        print("      pass --name / --school / --grade to fill them, or edit in Gmail.")

    svc = gmail_service()
    label_id, created_label = ensure_label(svc, args.label)
    print(f"label {args.label!r}: {'created' if created_label else 'already exists'}")

    existing = existing_draft_subjects(svc)
    made, skipped = 0, 0
    for e in prepared:
        if e["subject"] in existing:
            print(f"  skip  [{e['n']:2d}] already a draft: {e['subject'][:60]}")
            skipped += 1
            continue
        create_draft(svc, e["subject"], e["body"], label_id)
        print(f"  draft [{e['n']:2d}] {e['institution']}")
        made += 1

    print()
    print(f"{made} drafts created, {skipped} skipped, under label {args.label!r}.")
    print("Nothing was sent. Every draft has an empty To: field -- add the recipient")
    print("in Gmail once you have a named person, then read it once more before sending.")


if __name__ == "__main__":
    main()
