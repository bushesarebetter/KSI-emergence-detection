"""Locks scripts/gmail_drafts.py's parser to the format of docs/OUTREACH.md.

The script reads the emails out of the markdown rather than duplicating them, so
the two must agree. These tests fail the moment an edit to OUTREACH.md breaks the
`## N. Institution` / `> **Subject:**` structure the parser depends on -- which is
far better than discovering it after ten malformed drafts land in Gmail.

No Google libraries are imported: the script defers those to the point of use.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "gmail_drafts", ROOT / "scripts" / "gmail_drafts.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gd = _load()
EMAILS = gd.parse_outreach((ROOT / "docs" / "OUTREACH.md").read_text(encoding="utf-8"))


def test_finds_exactly_ten_emails():
    assert [e["n"] for e in EMAILS] == list(range(1, 11))


def test_every_email_has_a_subject_and_body():
    for e in EMAILS:
        assert e["subject"], f"email {e['n']} has no subject"
        assert len(e["body"]) > 200, f"email {e['n']} body is suspiciously short"


def test_no_markdown_quote_markers_leak_into_bodies():
    for e in EMAILS:
        assert "\n> " not in "\n" + e["body"], f"email {e['n']} still has blockquote markers"
        assert "**Subject:**" not in e["body"]


def test_bodies_open_with_a_salutation_and_close_with_the_signature_placeholder():
    for e in EMAILS:
        assert e["body"].startswith("Dear "), f"email {e['n']} does not start with a salutation"
        assert e["body"].rstrip().endswith("[YOUR NAME]"), f"email {e['n']} is missing the signature"


def test_placeholders_are_filled_and_recipient_ones_are_left_alone():
    subs = {
        "[YOUR NAME]": "Test Person",
        "[SCHOOL]": "Test High",
        "[GRADE]": "12",
        "[DASHBOARD URL]": "https://example.org",
    }
    for e in EMAILS:
        body = gd.fill(e["body"], subs)
        assert "[YOUR NAME]" not in body
        assert "[DASHBOARD URL]" not in body
        assert gd.unfilled(body) == []
    # Recipient-specific placeholders must survive: the user fills them per draft.
    faculty = next(e for e in EMAILS if "Professor" in e["body"])
    assert "[SPECIFIC PAPER]" in gd.fill(faculty["body"], subs)
    assert all("[Name]" in e["body"] for e in EMAILS)


def test_dashboard_url_default_is_the_live_site():
    assert gd.DEFAULT_URL.startswith("https://")
    assert "onrender.com" in gd.DEFAULT_URL


def test_script_source_never_calls_send():
    """The no-send guarantee lives in the code, not the OAuth scope -- so pin it."""
    src = (ROOT / "scripts" / "gmail_drafts.py").read_text(encoding="utf-8")
    assert ".send(" not in src
    assert "messages().send" not in src
    assert "drafts().send" not in src

def test_no_placeholder_is_split_across_a_line_break():
    """A placeholder hard-wrapped across two lines (as [SPECIFIC PAPER] once was)
    cannot be found by searching for the intact token, so it is the one most
    likely to be sent by accident. Built with chr(10) to keep the check free of
    backslash escapes."""
    import re
    pattern = re.compile(r"\[[A-Z][A-Z ]*" + chr(10) + r"[A-Z ]*\]")
    for e in EMAILS:
        split = pattern.findall(e["body"])
        assert not split, f"email {e['n']} has a placeholder wrapped across lines: {split}"


def test_flow_keeps_signoff_and_link_lines_separate():
    """Flowing must not glue the signature onto the closing line, nor merge a
    'Label: url' list into one line -- both would look careless to a recipient."""
    NL = chr(10)
    for e in EMAILS:
        flowed = gd.flow_paragraphs(e["body"])
        assert flowed.rstrip().endswith(NL + "[YOUR NAME]"), f"email {e['n']}: sign-off glued"
        assert "Dear " in flowed.split(NL)[0]
        assert (NL + NL) in flowed
    faculty = next(e for e in EMAILS if "Professor" in e["body"])
    flowed = gd.flow_paragraphs(faculty["body"])
    assert any(l.startswith("Interactive map:") for l in flowed.split(NL))
    assert any(l.startswith("Code and full write-up:") for l in flowed.split(NL))


def test_emails_credit_the_collaborator():
    """Authorship was resolved as joint work; every email must say so."""
    for e in EMAILS:
        assert "Ayan Pendharkar" in e["body"], f"email {e['n']} does not name the collaborator"


def test_flow_never_breaks_a_sentence_or_a_hyphenated_word():
    """Two defects that reached generated drafts once: a wrap inside a hyphenated
    word rejoined with a space, and a prose line beginning "The question:" kept
    as a label so the sentence broke across lines."""
    import re
    NL = chr(10)
    for e in EMAILS:
        flowed = gd.flow_paragraphs(e["body"])
        # Inside a paragraph, a newline may only be followed by a capital, a URL,
        # or a placeholder -- never by a lowercase continuation of a sentence.
        assert not re.search("[a-z,]" + NL + "[a-z]", flowed), f"email {e['n']}: broken sentence"
        assert not re.search("[a-z]- [a-z]", flowed), f"email {e['n']}: hyphen-space artefact"
        assert "killed-or- " not in flowed

