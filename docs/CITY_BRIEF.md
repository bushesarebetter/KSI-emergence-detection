# San Diego's next dangerous intersections — before the crashes

**A free, public map that ranks the intersections most likely to produce a serious crash in the
next three years — focused on the ones the City isn't watching yet.**

---

## The gap

San Diego fixes intersections *after* people are hurt. The City's annual review only flags
locations that already have **five or more injury-or-fatal crashes** — 14 of them in 2024. By
definition, an intersection can't make that list until the crashes have already happened.

This tool looks at the intersections **below that line** — the quiet-so-far corners — and ranks
them by how likely each is to become a serious-injury site within three years, using the crash
records, road design, and traffic patterns the City already has.

## Does it work?

Tested the honest way — the model is scored only on intersections it never saw during training,
and then checked against a **future year of real crash outcomes it had no access to**:

- A **top-500 shortlist** catches future serious-crash sites at about **7× the rate of guessing**.
- That result **held up on a held-out year (2025)** the model was never trained on.
- Every site on the list is one the City's 5-crash review does **not** flag.

It's a **prioritization tool, not a magic detector**: it mostly surfaces busier corridors with
recent crashes and higher-risk road design. But it turns "we'll get to it after someone's hurt"
into a ranked, forward-looking list the City can act on now — and it re-runs automatically every
time new crash data is released.

## It's local

The map filters by **council district**. Every district has 35–78 of the top-500 emerging-risk
intersections. A council office can open it and see *their* corners, by name, ranked, with the
reason each one is flagged. (Per-district lists: `results/by_council_district.csv`.)

## The ask

1. **Council offices** — review your district's top sites. These are candidates for low-cost,
   proven fixes (better signs, flashing beacons, crosswalks, signal timing) *before* a serious
   crash, not after.
2. **Advocates & planning groups** — use the list to push for treating sub-threshold locations
   systemically, the way the City already treats known high-crash sites.
3. **Grant support** — federal Safe Streets and Roads for All (SS4A) and HSIP programs require a
   data-driven safety analysis. This is that analysis, for the locations current screening misses.

The map, the code, and the methodology are open and free. Every number above is reproducible.

*Map: [dashboard URL] · Method and limits: `docs/HYPOTHESIS.md`*
