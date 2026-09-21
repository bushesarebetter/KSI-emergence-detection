# Review log

A simulated review, September 2026. Each entry takes one professional lens, lists what a
reviewer with that background would press on given the project as it stands, and records
what changed and what did not. These are reasoned from each field's published concerns,
not from anyone's actual reading of this work. Names of real people are not used as
authorities; the lenses are.

## 1. Decision science and AI (calibration, human-AI, ethics)

- **A rank is not a probability, and the site never said what a rank is worth.** Fixed: each
  corner's panel now states, from the export's own catch table, how often corners ranked
  that high had a serious crash in 2025 so far, with the raw counts ("9 of 500, against 62
  of 25,034"), and the About page says the rank is an ordering. Per-tier slices rest on one
  or two events and are not shown, and a ratio is withheld below three events: the top 50
  holds one 2025 positive, and "8 times the base rate" on one event is noise with a number
  on it. The counts are shown instead.
- **Over-trust in generic advice.** Kept: the advice sits next to the signals that produced
  it, and the About and terms say the actions are general practice.
- **No route for the system to learn from what engineers decide.** Fixed: a treatment log
  (`data/evaluation/treatments.csv`, `scripts/log_treatment.py`) records each review or
  fix that can be traced to the list, with its matched controls, as the evaluation plan
  requires.
- **Feedback loop: acting on the list changes the data the next model learns from.** Fixed
  in the plan: treated corners are flagged and excluded from later label windows.
- **Equity.** Fixed in part: the export check prints the top-800 count by district, and the
  evaluation plan adds subgroup analyses by district and by CalEnviroScreen quartile. Open:
  the site does not yet show a district's share of listed corners against its share of all
  intersections, because the export does not carry the candidate count per district.

## 2. City traffic engineer, Vision Zero programme

- **The school-zone law was misstated** (15 mph was given as the general limit). Fixed:
  25 mph when children are present, 15 mph where a 15 mph zone is posted.
- **Signal measures at unsignalised corners, and the reverse.** Already handled by control
  from OpenStreetMap; a corner with no control mapped is offered both, labelled.
- **"Engineering review" as a cost line.** Kept, labelled rough; it is the ask a council
  office can make.
- **The City's rule: all crashes or injury crashes?** The site uses five injury crashes in a
  year (DECISIONS.md D18, SWITRS severity 1 to 4); the README's headline says "reported
  crashes". Open for the authors to state once, in both places.
- **"A transit stop is 544 m away, so people cross here to reach it."** A seven-minute walk
  does not put anyone in this crosswalk. The model scores the stop at any distance (all
  302 such labels in the top 800 push risk up), but the crossing claim and the advice now
  stop at 250 m; beyond that the signal is shown as a distance and nothing more. 53 of the
  302 corners lose that advice.
- **The same intersection listed twice.** OpenStreetMap gives a divided road one node per
  carriageway, so 22 pairs in the top 800 sit within 30 m of each other (#6 and #491,
  12 m apart, same name). Fixed on the surface: the panel's nearby list names such a pair
  as "almost certainly the same intersection mapped twice", and the export check counts
  them. Open for the pipeline: merge nodes within about 25 m before ranking, so the list
  does not spend two of its 800 places on one corner.

## 3. Transportation safety researcher

- **2025 is a partial year.** Fixed: every figure sentence says "in 2025 so far".
- **Rates on all crashes include property-damage-only reports, which under-report.** Fixed:
  the injury-only rate per year is shown, and technical mode adds the fatal-and-injury rate
  per million entering vehicles; the CSV carries injury crashes a year and five-year counts
  by severity.
- **Regression to the mean.** Already the centre of the evaluation plan's matching design.
- **Confidence intervals on recall.** Present for the verified run in the About page; the
  forward run's are in the repository results. Open: show the bootstrap interval for the
  export's own catch at 800 once the pipeline writes it to `meta.json`.

## 4. HSIP grant reviewer

- **An application needs crash data by severity for five years, a CMF with its source, a
  cost and a service life.** Fixed: the CSV carries five-year PDO, injury and KSI counts and
  the injury rate; each measure now has a typical service life, shown in technical mode;
  the FHWA and CMF Clearinghouse sources are named. Open: the benefit-cost ratio itself,
  which needs FHWA's B and C injury costs the repository does not yet carry; the site hands
  over the inputs and says so.

## 5. Council office staff

- **A one-page sheet per corner that can be forwarded.** Fixed: `/corner/N` is a page with
  the advice, the record, the measures and a citation; it prints, embeds, and reads on a
  phone. The panel links to it.
- **An email address rather than a code-hosting issue tracker.** Open, the authors' call.

## 6. Data journalist

- **When was this data current?** Fixed: the sidebar states the crash-record cutoff, the
  traffic-count years, the police-report date and the model export date.
- **A single corner to embed or screenshot.** Fixed: `/corner/N`.
- **Where the numbers come from.** Present: the CSV, the methodology, the decision log, and
  a citation on every corner.
- **"Last crash ~1 years ago" in the technical table.** The export writes the label that
  way for 110 corners. The site tidies it on display; the pipeline should write it right.

## 7. Accessibility specialist

- **Keyboard users had to tab through the sidebar to reach the map.** Fixed: a skip link.
- **Copy confirmations were visual only.** Fixed: a polite live region announces them.
- **Focus was lost when a corner opened.** Fixed: focus moves to the corner's name.
- **Map dots are not keyboard-reachable.** Known and accepted: the table and the search box
  provide the same corners to the keyboard.

## 8. Privacy and legal

- **Naming a school near a listed corner.** Fixed: the terms say the name marks the
  crossing its pupils use and says nothing about the school.
- **Addresses typed into the route check.** Already stated: they go to Google and are not
  stored here.

## 9. Security

- **Data rendered as HTML in the map tooltip.** Fixed: names and districts are escaped.
- **No backend, no secrets in the client beyond the referrer-restricted map key.** Kept.

## 10. Resident, first visit

- **The panel led with a chart; the person wanted to know what to do.** Fixed: "If you use
  this corner" now comes before the case for fixing it.
- **The phone version had no way to act.** Fixed earlier: write to the council office from
  the sheet.

## What remains open, and why

- A benefit-cost ratio per corner (needs FHWA injury costs by KABCO class).
- A district's share of listed corners against its share of all intersections (needs
  candidate counts per district in the export).
- The bootstrap interval on the export's own catch (needs the pipeline to write it).
- One statement of the City's rule, all crashes or injury crashes, in README and site alike.
- Merging OpenStreetMap nodes within about 25 m before ranking (22 twin pairs in the top
  800), and writing "1 year" rather than "1 years" in the export's labels.
- An email contact, if the authors want one published.

Each of these is a pipeline or an authors' decision, not an interface change.
