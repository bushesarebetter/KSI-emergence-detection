/**
 * Everything about this deployment that is a fact about the place rather than
 * about the interface. Another county changes this file, its export, and
 * nothing else.
 */
export const SITE = {
  name: "San Diego",
  fullName: "City of San Diego",
  county: "San Diego County",
  siteTitle: "San Diego Food Safety Risk",
  shortTitle: "Food Safety Risk",
  siteUrl: "https://sd-food-safety-risk.onrender.com",

  center: { lat: 32.78, lng: -117.13 },
  bounds: { south: 32.53, west: -117.29, north: 33.12, east: -116.9 },

  // Council districts of the City of San Diego. A facility outside the City
  // has none, and the export leaves the field null.
  districts: { count: 9, label: "Council district", short: "District" },

  // Who inspects, and where their results and complaint line live. The County
  // inspects retail food facilities in every city in the county, the City of
  // San Diego included.
  regulator: {
    name: "San Diego County Department of Environmental Health and Quality",
    short: "the County",
    resultsUrl: "https://www.sandiegocounty.gov/content/sdc/deh/fhd/ffis.html",
    programUrl: "https://www.sandiegocounty.gov/content/sdc/deh/fhd/food/food.html",
    phone: "(858) 505-6700",
    // The County's own summary of its programme: roughly this many retail food
    // facilities, inspected one to three times a year by risk category.
    facilityCount: 14000,
    grades: { A: "90 to 100", B: "80 to 89", C: "79 or below" },
  },

  authors: "Chenhao Zhang and Ayan Pendharkar, Canyon Crest Academy, San Diego",
  citationAuthors: "Zhang, C., and Pendharkar, A.",
  attributions:
    "Inspection results: San Diego County Department of Environmental Health and Quality, SD Food Info. Basemap and Street View: Google Maps.",

  searchHint: "Try part of a name or a street, like Convoy.",
};

export const DISTRICT_NUMBERS = Array.from({ length: SITE.districts.count }, (_, i) => i + 1);
