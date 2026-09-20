/**
 * Everything about the dashboard that belongs to one city.
 *
 * The pipeline is adapter-based (configs/regions/*.yaml); this is the
 * front-end half of the same idea. A new city is a new object here plus its
 * data files under public/data, and nothing in the components names a place.
 * docs/NEW_CITY.md walks through it.
 */
export const CITY = {
  name: "San Diego",
  fullName: "City of San Diego",
  state: "California",
  siteTitle: "San Diego Intersection Risk",
  shortTitle: "Intersection Risk",
  siteUrl: "https://ksi-emergence-detection.onrender.com",

  // Map framing and address-lookup bias.
  center: { lat: 32.7157, lng: -117.1611 },
  bounds: { south: 32.53, west: -117.29, north: 33.12, east: -116.9 },

  // The city's own reactive review, which the ranking sits below (DECISIONS.md D18).
  screen: {
    name: "High Crash List",
    threshold: 5,
    unit: "injury crashes in a year",
    reviewsPerYear: 14,
  },

  // Political geography: who a resident writes to.
  districts: {
    count: 9,
    label: "Council District",
    short: "District",
    councilIndex: "https://www.sandiego.gov/citycouncil",
    councilUrl: (d) => `https://www.sandiego.gov/citycouncil/cd${d}`,
  },
  transportationDept: "the Transportation Department",
  visionZeroUrl: "https://www.sandiego.gov/vision-zero",

  // Credits and voice.
  authors: "Chenhao Zhang and Ayan Pendharkar, Canyon Crest Academy, San Diego",
  citationAuthors: "Zhang, C., and Pendharkar, A.",
  attributions:
    "Crash data: SWITRS via TIMS, UC Berkeley SafeTREC. Road network: OpenStreetMap contributors. Basemap and Street View: Google Maps.",
  crashDataThrough: "December 2024",
  searchHint: "Try one street name, like El Cajon or Genesee.",
};

export const DISTRICT_NUMBERS = Array.from({ length: CITY.districts.count }, (_, i) => i + 1);
