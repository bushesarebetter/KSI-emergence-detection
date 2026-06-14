export function formatPercentile(p) {
  const fixed = Number.isInteger(p) ? p : parseFloat(p.toFixed(1));
  const str = fixed % 1 === 0 ? String(Math.round(fixed)) : fixed.toFixed(1);
  const n = Math.round(fixed);
  if (n % 100 >= 11 && n % 100 <= 13) return `${str}th`;
  switch (n % 10) {
    case 1: return `${str}st`;
    case 2: return `${str}nd`;
    case 3: return `${str}rd`;
    default: return `${str}th`;
  }
}

export function formatDistrict(d) {
  return `District ${d}`;
}

export function formatScore(s) {
  return parseFloat(s).toFixed(2);
}

export function intersectionsToCsv(features) {
  const header = "rank,intersection_name,council_district,percentile,crashes_training,top_signal,is_crash_active,is_known_emergent,lon,lat";
  const rows = features.map((f) => {
    const p = f.properties;
    const name = p.intersection_name.includes(",")
      ? `"${p.intersection_name}"`
      : p.intersection_name;
    const topSignal = p.shap_features?.[0]?.display_label ?? "";
    const topSignalQuoted = topSignal.includes(",") ? `"${topSignal}"` : topSignal;
    const lon = f.geometry.coordinates[0];
    const lat = f.geometry.coordinates[1];
    return [
      p.rank, name, p.council_district, p.percentile,
      p.crashes_training, topSignalQuoted, p.is_crash_active,
      p.is_known_emergent, lon, lat,
    ].join(",");
  });
  return [header, ...rows].join("\n");
}
