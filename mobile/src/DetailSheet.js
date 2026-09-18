import { View, Text, ScrollView, Pressable, StyleSheet, Linking, Platform } from "react-native";
import { colors, riskColor, riskLabel } from "./theme";
import { formatPercentile } from "./lib/format";

function CrashHistoryBars({ history }) {
  const max = Math.max(1, ...history.map((y) => y.ksi + y.injury + y.pdo));
  return (
    <View style={s.chartRow}>
      {history.map((y) => {
        const total = y.ksi + y.injury + y.pdo;
        return (
          <View key={y.year} style={s.chartCol}>
            <View style={s.chartBarTrack}>
              <View
                style={[
                  s.chartBar,
                  {
                    height: `${(total / max) * 100}%`,
                    backgroundColor: y.ksi > 0 ? "#ef4444" : colors.accent,
                  },
                ]}
              />
            </View>
            <Text style={s.chartLabel}>{String(y.year).slice(2)}</Text>
          </View>
        );
      })}
    </View>
  );
}

function openMaps(lat, lon, mode) {
  // Prefer the native Google Maps app when it's installed; the https URLs below
  // are universal links that Google Maps claims on both platforms and that fall
  // back to the browser when it isn't.
  const urls = {
    map: `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`,
    pano: `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}`,
    dir: `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}&travelmode=driving`,
  };
  Linking.openURL(urls[mode]);
}

export default function DetailSheet({ site, onClose }) {
  if (!site) return null;
  const color = riskColor(site.rank);

  return (
    <View style={s.sheet}>
      <View style={s.grabber} />

      <View style={s.header}>
        <View style={{ flex: 1 }}>
          <View style={s.rankRow}>
            <Text style={[s.rank, { color }]}>#{site.rank}</Text>
            <Text style={s.rankOf}>of 26,045</Text>
          </View>
          <Text style={[s.riskLabel, { color }]}>
            {riskLabel(site.rank)} · {formatPercentile(site.percentile)} pct.
          </Text>
        </View>
        <Pressable onPress={onClose} hitSlop={12} accessibilityLabel="Close">
          <Text style={s.close}>×</Text>
        </Pressable>
      </View>

      <ScrollView style={s.body} contentContainerStyle={{ paddingBottom: 32 }}>
        <Text style={s.name}>{site.intersection_name}</Text>

        <View style={s.badges}>
          <Badge text={`District ${site.council_district}`} />
          <Badge
            text={site.is_crash_active ? "Crash active" : "Crash silent"}
            tone={site.is_crash_active ? "green" : "neutral"}
          />
          {site.is_known_emergent && <Badge text="2025 KSI positive" tone="orange" />}
        </View>

        <Section title="Crash history (2016–2025)">
          <CrashHistoryBars history={site.crash_history} />
        </Section>

        <Section title="Model signals">
          <Text style={s.caption}>All values as of Jan 1, 2025 (training cutoff)</Text>
          {site.shap_features.slice(0, 6).map((f) => (
            <View key={f.feature_name} style={s.shapRow}>
              <Text style={s.shapLabel} numberOfLines={1}>
                {f.display_label}
              </Text>
              <View style={s.shapTrack}>
                <View
                  style={[
                    s.shapFill,
                    {
                      width: `${Math.min(
                        100,
                        (Math.abs(f.shap_value) /
                          Math.abs(site.shap_features[0].shap_value)) * 100
                      )}%`,
                      backgroundColor: f.shap_value >= 0 ? colors.accent : "#38bdf8",
                    },
                  ]}
                />
              </View>
            </View>
          ))}
        </Section>

        <Section title="View this site">
          <Action label="Street View" onPress={() => openMaps(site.lat, site.lon, "pano")} />
          <Action label="Open in Google Maps" onPress={() => openMaps(site.lat, site.lon, "map")} />
          <Action label="Directions" onPress={() => openMaps(site.lat, site.lon, "dir")} />
        </Section>
      </ScrollView>
    </View>
  );
}

const Section = ({ title, children }) => (
  <View style={s.section}>
    <Text style={s.sectionTitle}>{title}</Text>
    {children}
  </View>
);

const Badge = ({ text, tone = "neutral" }) => {
  const tones = {
    neutral: [colors.surfaceAlt, colors.textMuted],
    green: ["#052e1a", "#4ade80"],
    orange: ["#3b1a05", "#fb923c"],
  };
  const [bg, fg] = tones[tone];
  return (
    <View style={[s.badge, { backgroundColor: bg }]}>
      <Text style={[s.badgeText, { color: fg }]}>{text}</Text>
    </View>
  );
};

const Action = ({ label, onPress }) => (
  <Pressable style={s.action} onPress={onPress}>
    <Text style={s.actionText}>{label}</Text>
    <Text style={s.actionChevron}>›</Text>
  </Pressable>
);

const s = StyleSheet.create({
  sheet: {
    position: "absolute", left: 0, right: 0, bottom: 0, height: "62%",
    backgroundColor: colors.surface,
    borderTopLeftRadius: 18, borderTopRightRadius: 18,
    borderTopWidth: 1, borderColor: colors.border,
    ...Platform.select({
      ios: { shadowColor: "#000", shadowOpacity: 0.5, shadowRadius: 20, shadowOffset: { width: 0, height: -6 } },
      android: { elevation: 24 },
    }),
  },
  grabber: { alignSelf: "center", width: 36, height: 4, borderRadius: 2, backgroundColor: colors.border, marginTop: 8 },
  header: { flexDirection: "row", alignItems: "flex-start", paddingHorizontal: 18, paddingTop: 12, paddingBottom: 12, borderBottomWidth: 1, borderColor: colors.border },
  rankRow: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  rank: { fontSize: 26, fontWeight: "700", fontVariant: ["tabular-nums"] },
  rankOf: { fontSize: 11, color: colors.textFaint },
  riskLabel: { fontSize: 12, fontWeight: "500", marginTop: 2 },
  close: { fontSize: 28, lineHeight: 30, color: colors.textFaint, paddingHorizontal: 4 },
  body: { paddingHorizontal: 18 },
  name: { fontSize: 15, fontWeight: "600", color: colors.text, marginTop: 16, lineHeight: 21 },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 12 },
  badge: { borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5, borderWidth: 1, borderColor: colors.border },
  badgeText: { fontSize: 11, fontWeight: "500" },
  section: { marginTop: 24 },
  sectionTitle: { fontSize: 10, fontWeight: "700", color: colors.textFaint, letterSpacing: 1.4, textTransform: "uppercase", marginBottom: 10 },
  caption: { fontSize: 10, color: colors.textFaint, marginBottom: 12 },
  chartRow: { flexDirection: "row", gap: 6, height: 90, alignItems: "flex-end" },
  chartCol: { flex: 1, alignItems: "center" },
  chartBarTrack: { width: "100%", height: 70, justifyContent: "flex-end", backgroundColor: colors.surfaceAlt, borderRadius: 3, overflow: "hidden" },
  chartBar: { width: "100%", borderRadius: 3 },
  chartLabel: { fontSize: 9, color: colors.textFaint, marginTop: 5 },
  shapRow: { marginBottom: 10 },
  shapLabel: { fontSize: 12, color: colors.textMuted, marginBottom: 4 },
  shapTrack: { height: 5, backgroundColor: colors.surfaceAlt, borderRadius: 999, overflow: "hidden" },
  shapFill: { height: "100%", borderRadius: 999 },
  action: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: 13, borderBottomWidth: 1, borderColor: colors.border },
  actionText: { fontSize: 14, color: colors.text },
  actionChevron: { fontSize: 20, color: colors.textFaint },
});
