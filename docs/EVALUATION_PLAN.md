# Evaluation plan: does acting on the list reduce crashes?

*Pre-registration draft, September 2026. To be registered on the Open Science Framework
before the first treated corner is known. Authors: Chenhao Zhang and Ayan Pendharkar.*

## The question

When a corner on this list is reviewed or fixed because it was on the list, do crashes
there fall more than at comparable corners that were not acted on? Everything else the
project claims is about the ranking. This is the only claim a City or a state will adopt on,
so it is written down before any corner is treated.

## Units and treatment

- **Unit:** one intersection in the exported list (top 1,000 of the current model export),
  identified by its coordinates.
- **Treated:** an engineering review was requested, or a countermeasure installed, and the
  request can be traced to the list (a council office, the Transportation Department or a
  grant application cites the map or the corner's rank). Date of treatment is the date the
  countermeasure is in place; a review alone counts as treated only if it produced a change
  on the ground.
- **Control:** listed corners with no review and no change over the same period.

## Matching

Each treated corner is matched, before outcomes are read, to up to three control corners
from the same export that agree on:

1. rank stratum (1 to 100, 101 to 300, 301 to 800, 801 to 1,000);
2. control type from OpenStreetMap (signals, stop, none);
3. daily traffic within a factor of two where the City has a count on both;
4. council district where possible, else adjacent district.

Matches are fixed at the time of treatment and never revised. Corners that become treated
later leave the control pool from that date.

## Outcomes

- **Primary:** injury crashes (SWITRS severity 1 to 4) in the 24 months after treatment,
  versus the 24 months before, at treated corners and their matches.
- **Secondary:** all police-reported crashes at the intersection (City open data,
  intersection-filed reports only) in the same windows, available months earlier than
  SWITRS.
- **Not an outcome:** the model's rank. A corner that was fixed and then drops in rank
  proves nothing on its own.

## Analysis

A difference-in-differences comparison of the change in crash counts at treated corners
against the change at matched controls, fit as a negative binomial regression with corner
fixed effects and a treatment-by-period term, clustered by matched set. Regression to the
mean is the main threat: corners are listed partly because their recent counts rose, so
controls must come from the same list, which is why they do.

## Power, stated honestly

Listed corners average about 1.5 crashes a year. With 30 treated corners, three matches
each and two-year windows, the design can detect roughly a 35 to 40 percent reduction in
injury crashes at conventional significance. Smaller true effects, which are what a leading
pedestrian interval produces, will not be detectable; for those the plan reports the
estimate and its interval rather than a verdict. Ten treated corners will not settle
anything and the plan says so in advance.

## Equity

Crash counts under-report where crashes are reported less, and exposure-normalised rates
favour quiet streets. Two checks run alongside the primary analysis: the distribution of
listed and of treated corners across council districts against each district's share of
candidate intersections, and the same by CalEnviroScreen quartile of the surrounding
tract. A treatment effect that holds only in the better-off half of the city is reported
as such.

## The feedback loop

A corner that is treated because it was listed will, if the treatment works, produce
fewer crashes and fall in later rankings. That is the desired outcome and a training
hazard: later models would learn that listed corners are safe. Treated corners are
therefore recorded in the treatment log, excluded from the label window of any model
trained after their treatment date, and never used to score the model.

## What would count against the project

- Treated corners fall no more than controls.
- Treated corners fall, but so do controls, by the same amount: the list found corners at
  a peak, which is the regression-to-the-mean result the matching exists to expose.
- Treatment can be traced to the list at fewer than ten corners in two years: the project
  did not move anything, whatever the model's recall.

## Data and timing

- Treatment log: kept in `data/evaluation/treatments.csv` with corner key, treatment, date,
  source of the trace, and the matched controls chosen at that date.
- Crash outcomes: SWITRS via TIMS (annual), police reports (weekly).
- First read: 24 months after the tenth treated corner. Interim reads are reported as
  interim and do not change the plan.

## Registration

This document is the plan. Any change after registration is recorded here as a dated
amendment with the reason, and the amended version is what the results cite.
