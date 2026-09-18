# Outreach plan

Ten institutions, grouped local → regional → national, with a ready-to-send email
for each. Send in that order: local agencies give you the operational reality check
that makes the regional and national emails stronger, and a reply from the City is
the single most useful thing you can cite to everyone else.

## Before you send anything

- **Fill in the placeholders.** `[YOUR NAME]`, `[SCHOOL]`, `[GRADE]`, `[DASHBOARD URL]`.
- **Authorship is joint.** The emails name Ayan Pendharkar as collaborator. `README.md`'s
  citation block still credits only Pendharkar — add Zhang before anyone follows the
  GitHub link.
- **Find a real person.** Every email below is addressed to a role. Ten minutes on
  the agency's staff directory or LinkedIn beats `info@`. A named recipient roughly
  doubles reply rates, and a wrong-but-close name usually gets forwarded internally.
- **Never send an attachment on a first email.** Attachments from unknown senders
  get quarantined by government mail filters. One link, in the body.
- **The dashboard must be live first.** See `docs/HOSTING_RENDER.md`. Half of these
  recipients will click the link and nothing else.
- **State the limits as findings.** The model's edge over a one-line crash-count baseline is
  modest, and it has no signal at the fatal/severe (≥2-KSI) threshold. Say so plainly —
  reviewers will find it in ten minutes, and stating it yourself is what makes the rest credible.
- **Keep the two runs straight.** The **verified run** is 25,699 candidates / 276 injury-crash
  positives / 39 caught at top-500 (2016–21 features → 2022–24 labels); the **forward run** is
  25,034 candidates / 62 positives (2025 partial) / 9 caught at top-500. Never quote a hit count
  from one alongside a candidate count from the other. Source: `README.md`, `docs/HYPOTHESIS.md`.
- **Expect silence.** Agency inboxes are brutal. A single short follow-up after 10–14
  working days is normal and not rude. Two is pushing it.

---

# LOCAL — City and county of San Diego

## 1. City of San Diego, Transportation Department (Vision Zero program)

**Why them:** They own the annual screening process this project is built as a
complement to, and they are the only body that can actually treat these
intersections. This is the most important email on the list.
**Find:** sandiego.gov → Transportation Department → Vision Zero. Ask for the
Vision Zero program manager or the traffic engineering supervisor who runs the
annual safety screening.
**Ask:** a 20-minute conversation and a reality check on the candidate list.

> **Subject:** Student research: predicting which SD intersections become severe-crash sites before they do
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. Over the past year my collaborator
> Ayan Pendharkar and I built a model that tries to identify San Diego intersections likely to produce a killed-or-
> serious-injury crash within three years — restricted to intersections with no
> severe-crash history, so they're invisible to a screen based on prior crashes.
>
> It uses SWITRS records the City already has, plus road infrastructure and the crash pattern
> in each intersection's surrounding corridor. On a genuinely held-out test, a top-500 shortlist
> out of 25,699 candidate intersections caught 39 of the sites that went on to become
> injury-crash locations, about 7 times better than chance. A prospective test against 2025
> outcomes the model never saw held that same 7x concentration.
>
> Two things worth stating plainly: the model's edge over a simple crash-count-and-trend rule is
> modest, and it has no signal at the fatal/severe threshold, where crashes are too rare to
> predict. Its value is the injury-crash shortlist, on sites your five-crash screen never surfaces.
>
> Map and full methodology: [DASHBOARD URL]
>
> Would someone on your team be willing to spend 20 minutes telling me where this is
> wrong? Specifically: does the top-50 list contain locations you'd already flagged
> through other channels, and are there sites on it your engineers would immediately
> rule out? That kind of feedback would improve the work more than anything we can do
> on our own.
>
> Thank you for your time,
> [YOUR NAME]

---

## 2. SANDAG (San Diego Association of Governments)

**Why them:** Regional planning authority, runs the regional travel demand model,
and holds the traffic-count data the model is currently missing. `docs/MODEL_IMPROVEMENTS.md`
identifies exposure/AADT as the single largest known gap — SANDAG can close it.
**Find:** Research & Program Management, or the Regional Planning / Safety group.
**Ask:** access to intersection-level traffic volume estimates.

> **Subject:** Student researcher — request for regional traffic count data (intersection safety model)
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. My collaborator Ayan Pendharkar
> and I have built an open-source model that predicts which San Diego intersections
> without severe-crash history are most likely to develop one, using SWITRS crash
> records: [DASHBOARD URL]
>
> The model currently has a known weakness we'd like to fix. It uses raw crash counts
> with no exposure denominator, which means it can't distinguish a genuinely
> dangerous intersection from a merely busy one. Every Highway Safety Manual safety
> performance function normalises by AADT for exactly this reason.
>
> Does SANDAG publish or share intersection-level or link-level volume estimates for
> the City of San Diego — either from the regional travel demand model or from count
> programs? Even coarse arterial-level AADT would let me model crash *rate* rather
> than crash count, which we expect is the largest single improvement available to
> this project.
>
> Everything is open source (MIT) and I'd be glad to share results, credit SANDAG as
> a data source, or present what I find.
>
> Thank you,
> [YOUR NAME]

---

## 3. Circulate San Diego

**Why them:** The region's main street-safety advocacy nonprofit; they publish
their own Vision Zero analyses and work directly with City Council. They move
faster than agencies and are far more likely to reply to a student.
**Find:** circulatesd.org → staff page → policy or advocacy director.
**Ask:** feedback, and whether the shortlist is useful to their advocacy.

> **Subject:** Open-source model for predicting SD intersection crash risk — would this be useful to you?
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL], and I've been following Circulate's
> Vision Zero work while building something adjacent to it with my collaborator
> Ayan Pendharkar.
>
> We built a model that ranks the roughly 26,000 San Diego intersections with no
> severe-crash history by how likely they are to produce a killed-or-serious-injury
> crash in the next three years. The point is to get ahead of the City's current
> screen, which flags intersections with five or more prior crashes and so by
> definition can't see a location until after people have been hurt there.
>
> The map is public and filterable by Council district: [DASHBOARD URL]
>
> I'd value your read on two things. First, is a ranked pre-crash list actually
> useful in advocacy, or does the absence of a crash history make it too easy for an
> agency to dismiss? Second, the district-level breakdown shows a concentration that
> I suspect maps onto existing equity patterns in the region — you'd know far better
> than I would whether that's a story worth telling carefully.
>
> Everything is open source and free to use or critique.
>
> Thanks,
> [YOUR NAME]

---

## 4. County of San Diego, Health & Human Services Agency — Injury Prevention

**Why them:** Public-health framing of road trauma, and they hold the injury
outcome data that complements SWITRS police reports. A different constituency than
the engineers, and often more receptive to a prevention argument.
**Find:** Public Health Services → Injury & Violence Prevention.
**Ask:** whether prediction is useful for prevention targeting.

> **Subject:** Student research on predicting severe traffic injuries before they occur
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. My collaborator Ayan Pendharkar and
> I have built a model that identifies San Diego intersections at elevated risk of producing a killed-or-serious-injury
> crash within three years — before any severe crash has occurred there.
>
> Most traffic safety spending is reactive: a location gets attention after people
> are hurt. That's a prevention gap that I think reads more naturally in public
> health terms than in engineering terms. Using FHWA's crash cost figures, treating the sites a
> top-500 shortlist catches would prevent roughly $62M in harm over a three-year window, an
> estimated benefit-cost ratio near 19:1 after federal HSIP funding.
>
> Map and methodology: [DASHBOARD URL]
>
> I'd be grateful for 15 minutes with someone in Injury Prevention on whether a
> predictive site list is actionable from a public health standpoint, and whether
> linking SWITRS police reports to hospital discharge or trauma registry data is
> something the County has done or would consider. Severity misclassification in
> police-reported data is a known weakness of our labels.
>
> Thank you,
> [YOUR NAME]

---

## 5. UC San Diego — Urban Studies & Planning / SDSU Civil Engineering

**Why them:** Nearest academic home for this work, and the most likely source of
sustained mentorship. A faculty sponsor also makes every other email on this list
land harder.
**Find:** Pick a specific professor whose published work is on transportation
safety, spatial statistics, or urban analytics. **Read one of their papers first**
and reference it — a generic email to a professor gets deleted.
**Ask:** mentorship / feedback on methodology.

> **Subject:** High school student seeking feedback on a crash-prediction model (spatial CV question)
>
> Dear Professor [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. I read your work on
> [SPECIFIC PAPER] and hoped you might be willing to look at something my collaborator Ayan Pendharkar and I have built.
>
<<<<<<< HEAD
> I've spent the past year on a model predicting which San Diego intersections below the City's
> crash screen will produce a killed-or-serious-injury crash within three years. XGBoost with a
> Tweedie objective on 47 features — crash history, road infrastructure, and spatial-neighbor
> structure — evaluated with genuine out-of-fold scoring under both random and spatial-block CV,
> and a prospective test against 2025 outcomes the model never saw.
>
> The pattern I'd value your read on: crash-history features alone rank no better than a two-term
> persistence baseline; road infrastructure and the surrounding corridor's crash pattern are what
> push the model above it, by a modest margin that holds on both splits. With a few hundred
> positives the bootstrap intervals are wide, so the case rests on consistency across splits and
> windows rather than a single significant gap. I'd like to know whether that reasoning holds up.
=======
> We've spent the past year on a model predicting which San Diego intersections with
> no severe-crash history will produce a killed-or-serious-injury crash within three
> years. XGBoost with a Tweedie objective on 20 crash-history features, evaluated
> with genuine out-of-fold scoring under both random and spatial-block CV, and a
> prospective test against 2025 outcomes the model never saw.
>
> The result we keep getting stuck on: a two-term persistence baseline ties the tuned
> model at the severe threshold. We have 21 positive examples, so every comparison has
> bootstrap CIs wide enough to swallow any effect. We've written up twelve candidate
> improvements and my honest read is that the constraint is label sparsity, not
> architecture — but I'd very much like to know if I'm reasoning about that correctly.
>>>>>>> 63e230a87f95693ce4cfe0e7f46366d55a84a591
>
> Code and full write-up: https://github.com/bushesarebetter/KSI-emergence-detection
> Interactive map: [DASHBOARD URL]
>
> If you have 20 minutes to tell me what a reviewer would object to, I'd be grateful.
> I'm equally happy to hear that the approach is a dead end, if it is.
>
> Respectfully,
> [YOUR NAME]

---

# REGIONAL — California

## 6. Caltrans District 11

**Why them:** They own the state highway network in San Diego County and administer
HSIP funds locally. The project explicitly *excludes* state highways
(`exclude_state_highway: true`), which is a point in your favour — you're not
duplicating their work, you're covering what they don't.
**Find:** District 11 Traffic Operations / Safety, or the HSIP coordinator.
**Ask:** methodological feedback and HSIP framing.

> **Subject:** Student-built predictive screening model for surface-street intersections (District 11)
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. My collaborator Ayan Pendharkar
> and I have built an open-source model that screens City of San Diego surface-street
> intersections for severe-crash risk
> before any severe crash has occurred there. State highway crashes are excluded
> throughout, so this is complementary to District 11's network rather than
> overlapping it.
>
> It's trained on SWITRS via TIMS, uses out-of-fold evaluation on both random and
> spatial-block splits, and has been tested prospectively against 2025 outcomes it
> never saw during training: the top-500 shortlist held roughly a 7x concentration of
> future injury-crash sites over chance.
>
> [DASHBOARD URL]
>
> Two questions I'd value your view on. First, would a predictive shortlist of sites
> with no crash history be fundable under HSIP, or does the benefit-cost methodology
> effectively require documented crash history? Second, are there systematic SWITRS
> geocoding issues in District 11 I should know about? We found that POINT_X/POINT_Y
> is reliable where LATITUDE/LONGITUDE is not, and I'd like to know what else we're
> likely to be getting wrong.
>
> Thank you for your time,
> [YOUR NAME]

---

## 7. UC Berkeley SafeTREC (Safe Transportation Research & Education Center)

**Why them:** They operate TIMS — the exact system this project's data comes from.
They run the Street Story program and actively publish student-accessible research.
Among the highest-probability replies on this list.
**Find:** safetrec.berkeley.edu → people. Research associates reply more than
directors do.
**Ask:** methodological review; possible write-up or student showcase.

> **Subject:** TIMS-based intersection emergence model — methodology feedback from a high school researcher
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. My collaborator Ayan Pendharkar and I
> have used TIMS extensively over the past year; I wanted to share what we built with
> it and ask for your critique.
>
> The question: can you predict which San Diego intersections below the City's crash screen will
> produce a KSI crash in the next three years? Model is XGBoost-Tweedie on 47 features — crash
> history, road infrastructure, and spatial-neighbor structure — over 25,699 candidate
> intersections, scored entirely out-of-fold, with a prospective 2025 test the model never trained on.
>
<<<<<<< HEAD
> The finding I'd most like your reaction to: crash history alone ranks no better than a
> persistence baseline (crash count and trend); the lift comes entirely from infrastructure and
> corridor context, and it is modest — a few sites on 40 at top-500, consistent across both
> splits. The severe (≥2-KSI) threshold has too few positives to model. The edge is real and
> small, not a large ML win.
=======
> The finding I'd most like your reaction to is a negative one. At the ≥2-KSI
> threshold a persistence baseline — rank by recent crash count and trend — ties the
> tuned model exactly (10/21 both). The model only shows a consistent edge at the
> broader ≥1-KSI threshold. With 21 positives we can't distinguish "ML adds nothing
> here" from "our sample is too small to tell", and we've written up the twelve things
> we'd try next.
>>>>>>> 63e230a87f95693ce4cfe0e7f46366d55a84a591
>
> Code: https://github.com/bushesarebetter/KSI-emergence-detection
> Map: [DASHBOARD URL]
>
> If SafeTREC has interest in student work of this kind, or if someone there would
> spend 20 minutes poking holes in it, I'd be genuinely grateful. A separate
> question: is there an approved path to obtaining statewide SWITRS for research,
> so we could train across multiple cities and get past the sample size problem?
>
> Thank you,
> [YOUR NAME]

---

## 8. California Office of Traffic Safety (OTS)

**Why them:** They fund local traffic safety programs statewide and publish the OTS
crash rankings that cities are measured against. A predictive complement to a
retrospective ranking is directly on-mission.
**Find:** ots.ca.gov → Research and Evaluation, or a regional coordinator.
**Ask:** whether predictive screening fits their grant framework.

> **Subject:** Predictive complement to OTS crash rankings — student research
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. My collaborator Ayan Pendharkar
> and I have built an open-source model that ranks San Diego intersections by
> predicted future severe-crash risk, focused
> specifically on locations with no severe-crash history yet.
>
> The OTS rankings, like most safety screening, are retrospective by design — they
> tell a city where harm has already concentrated. What we've tried to build is the
> forward-looking complement: which currently-clean locations are trending toward
> becoming those sites. On a held-out test the top 500 of 25,699 candidates caught 39 of the
> intersections that subsequently became injury-crash sites, about 7x the rate of chance.
>
> [DASHBOARD URL]
>
> My question is whether this kind of predictive screening has a place in OTS's grant
> framework. Are there programs where a city could justify treating a location on
> predicted rather than observed risk? And is there interest at OTS in this being
> extended beyond San Diego? The method needs only SWITRS and OpenStreetMap, so it
> should port to any California city — and more cities would substantially fix the
> sample-size problem that currently limits what we can conclude.
>
> Thank you,
> [YOUR NAME]

---

# NATIONAL

## 9. FHWA Office of Safety — Safe Streets and Roads for All (SS4A)

**Why them:** SS4A explicitly funds "supplemental safety planning" and proactive
systemic analysis, and FHWA's own crash cost figures (FHWA-SA-25-021) are already
what this project's benefit-cost numbers are built on.
**Find:** SS4A program contacts on highways.dot.gov, or the FHWA California Division
safety engineer.
**Ask:** does this fit the systemic safety framework.

> **Subject:** Systemic safety analysis using crash history alone — student research, San Diego
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. My collaborator Ayan Pendharkar
> and I have built an open-source predictive screening model for San Diego
> intersections, and I think it sits close to
> FHWA's systemic safety approach, so I wanted to ask whether I'm reading that
> correctly.
>
> The model ranks roughly 25,700 intersections below the City's crash screen by predicted
> likelihood of a KSI crash within three years, using crash records, road infrastructure, and
> corridor context. Benefit-cost with FHWA-SA-25-021 crash costs in 2024 dollars is about 19:1
> at the top-500, after 90% HSIP federal funding.
>
> [DASHBOARD URL] · https://github.com/bushesarebetter/KSI-emergence-detection
>
> Where I'd value guidance: FHWA's systemic approach identifies risk *factors* and
> treats all locations sharing them. Our model ranks individual locations by predicted
> risk instead. Are those compatible framings for SS4A or HSIP purposes, or is
> location-level prediction outside what the systemic framework contemplates?
>
<<<<<<< HEAD
> The model's edge over a simple crash-count-and-trend heuristic is modest, and it has no signal
> at the fatal/severe threshold. The value is the injury-crash shortlist, on sites the crash
> screen does not surface.
=======
> I'd also note honestly that at the severe threshold a simple crash-count-and-trend
> heuristic matches our model's performance. If the practical answer is that
> agencies should use the simple rule, that seems worth knowing too.
>>>>>>> 63e230a87f95693ce4cfe0e7f46366d55a84a591
>
> Respectfully,
> [YOUR NAME]

---

## 10. Vision Zero Network

**Why them:** National coordinating body for Vision Zero cities. They amplify
practitioner-useful tools and their audience is exactly the set of cities that
could adopt this. Lower barrier than a federal agency.
**Find:** visionzeronetwork.org → team, or their general contact with a specific
subject line.
**Ask:** visibility, and connections to other Vision Zero cities.

> **Subject:** Open-source tool: predicting Vision Zero priority sites before the first severe crash
>
> Dear [Name],
>
> I'm [YOUR NAME], a [GRADE] student at [SCHOOL]. My collaborator Ayan Pendharkar and
> I have built a free, open-source tool that I think addresses a gap Vision Zero cities run into constantly, and I'd like
> your view on whether it's useful beyond San Diego.
>
> High-injury networks are built from crashes that have already happened. That's the
> right foundation, but it means a location can only become a priority after someone
<<<<<<< HEAD
> is seriously hurt there. My model ranks intersections below the City's crash screen by
> predicted risk over the next three years. On a held-out test, a top-500 shortlist out of
> 25,699 caught 39 of the sites that went on to become injury-crash locations, about 7x the
> rate of chance.
=======
> is seriously hurt there. Our model ranks intersections with *no* severe-crash
> history by predicted risk over the next three years. On a held-out test, a top-500
> shortlist out of 26,423 caught about 48% of the sites that went on to become
> severe-crash locations (10 of 21).
>>>>>>> 63e230a87f95693ce4cfe0e7f46366d55a84a591
>
> It needs only two public inputs — state crash records and OpenStreetMap — so it
> should replicate in any US city with a comparable crash database.
>
> [DASHBOARD URL] · MIT licensed: https://github.com/bushesarebetter/KSI-emergence-detection
>
> Two questions. Is a predictive complement to the high-injury network something your
> member cities would actually use, or does acting before a crash create political
> problems I'm not seeing? And would you be open to connecting us with a city willing
> to let us test the method on their data? More cities is the clearest path past the
> small-sample limits on what we can currently claim.
>
> Thank you,
> [YOUR NAME]

---

## Tracking

| # | Institution | Tier | Primary ask | Sent | Reply | Next step |
|---|---|---|---|---|---|---|
| 1 | City of San Diego Transportation | Local | Review the shortlist | | | |
| 2 | SANDAG | Local | AADT / volume data | | | |
| 3 | Circulate San Diego | Local | Advocacy feedback | | | |
| 4 | County HHSA Injury Prevention | Local | Public health framing | | | |
| 5 | UCSD / SDSU faculty | Local | Mentorship | | | |
| 6 | Caltrans District 11 | Regional | HSIP fundability | | | |
| 7 | UC Berkeley SafeTREC | Regional | Method review, statewide data | | | |
| 8 | California OTS | Regional | Grant framework fit | | | |
| 9 | FHWA Office of Safety | National | Systemic-safety fit | | | |
| 10 | Vision Zero Network | National | Visibility, partner cities | | | |

**Suggested sequence:** 7 and 5 first — SafeTREC and a faculty contact are the most
likely to reply and the least costly if the pitch needs adjusting. Use what you
learn to tighten 1 and 2, which are the two that could change what the City
actually does. Send 9 and 10 last, once you can open with "I've been in touch with
SafeTREC and the City of San Diego."

**Three further options** if you want more volume: the Transportation Research Board
standing committee on safety performance analysis (ANB25), which takes student
paper submissions; the Insurance Institute for Highway Safety, whose research group
works on exactly this class of problem; and the National Association of City
Transportation Officials (NACTO), which reaches city engineers directly.
