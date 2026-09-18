import { useState, useMemo, useRef, useCallback } from "react";
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from "react-native";
import MapView, { Marker, Circle, PROVIDER_GOOGLE } from "react-native-maps";
import * as Location from "expo-location";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import useIntersections from "./useIntersections";
import DetailSheet from "./DetailSheet";
import { colors, riskColor } from "./theme";
import { haversineMiles } from "./lib/format";

const SAN_DIEGO = {
  latitude: 32.7157,
  longitude: -117.1611,
  latitudeDelta: 0.35,
  longitudeDelta: 0.35,
};

const THRESHOLDS = [50, 100, 200, 500];

// Rendering 500+ native markers at once is visibly janky on mid-range Android.
// Markers are only drawn once the viewport is tight enough that the count in
// view is manageable; above that the map shows the "zoom in" hint instead.
const MARKER_ZOOM_DELTA = 0.22;

export default function MapScreen() {
  const { intersections, loading, error, reload } = useIntersections();
  const [threshold, setThreshold] = useState(200);
  const [selected, setSelected] = useState(null);
  const [region, setRegion] = useState(SAN_DIEGO);
  const mapRef = useRef(null);
  const insets = useSafeAreaInsets();

  const shown = useMemo(() => {
    if (!intersections) return [];
    return intersections.filter((d) => d.rank <= threshold);
  }, [intersections, threshold]);

  const markersVisible = region.latitudeDelta <= MARKER_ZOOM_DELTA;

  const inView = useMemo(() => {
    if (!markersVisible) return [];
    const latPad = region.latitudeDelta * 0.6;
    const lonPad = region.longitudeDelta * 0.6;
    return shown.filter(
      (d) =>
        Math.abs(d.lat - region.latitude) < latPad &&
        Math.abs(d.lon - region.longitude) < lonPad
    );
  }, [shown, region, markersVisible]);

  const goToMe = useCallback(async () => {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") return;
    const pos = await Location.getCurrentPositionAsync({});
    const { latitude, longitude } = pos.coords;

    // Centre on the user, then select whichever shortlisted site is closest, so
    // the sheet answers "what is the risk near me" in a single tap.
    mapRef.current?.animateToRegion(
      { latitude, longitude, latitudeDelta: 0.05, longitudeDelta: 0.05 },
      600
    );
    if (shown.length) {
      const nearest = shown.reduce((best, d) => {
        const dist = haversineMiles(latitude, longitude, d.lat, d.lon);
        return !best || dist < best.dist ? { d, dist } : best;
      }, null);
      setSelected(nearest.d);
    }
  }, [shown]);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator color={colors.accent} />
        <Text style={s.centerText}>Loading intersections...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={s.center}>
        <Text style={s.errorTitle}>Could not load data</Text>
        <Text style={s.centerText}>{error}</Text>
        <Pressable style={s.retry} onPress={reload}>
          <Text style={s.retryText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={s.root}>
      <MapView
        ref={mapRef}
        // Force the Google renderer on iOS too, so both platforms show the same
        // basemap as the web dashboard. Without this, iOS silently uses Apple Maps.
        provider={PROVIDER_GOOGLE}
        style={StyleSheet.absoluteFill}
        initialRegion={SAN_DIEGO}
        onRegionChangeComplete={setRegion}
        showsUserLocation
        showsMyLocationButton={false}
        customMapStyle={DARK_MAP_STYLE}
        toolbarEnabled={false}
        onPress={() => setSelected(null)}
      >
        {inView.map((d) => (
          <Marker
            key={d.id}
            coordinate={{ latitude: d.lat, longitude: d.lon }}
            onPress={(e) => {
              e.stopPropagation();
              setSelected(d);
            }}
            tracksViewChanges={false}
            anchor={{ x: 0.5, y: 0.5 }}
          >
            <View
              style={[
                s.dot,
                {
                  backgroundColor: riskColor(d.rank),
                  borderColor: selected?.id === d.id ? "#fff" : "rgba(255,255,255,0.35)",
                  borderWidth: selected?.id === d.id ? 2.5 : 1.5,
                },
              ]}
            />
          </Marker>
        ))}

        {selected && (
          // 76.2 m is the crash-assignment buffer the features are built on, so
          // drawing it makes clear which crashes are attributed to this node.
          <Circle
            center={{ latitude: selected.lat, longitude: selected.lon }}
            radius={76.2}
            strokeColor="rgba(249,115,22,0.8)"
            fillColor="rgba(249,115,22,0.12)"
            strokeWidth={1.5}
          />
        )}
      </MapView>

      <View style={[s.topBar, { paddingTop: insets.top + 8 }]}>
        <Text style={s.title}>KSI Emergence</Text>
        <View style={s.chips}>
          {THRESHOLDS.map((t) => (
            <Pressable
              key={t}
              onPress={() => setThreshold(t)}
              style={[s.chip, threshold === t && s.chipActive]}
            >
              <Text style={[s.chipText, threshold === t && s.chipTextActive]}>Top {t}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      {!markersVisible && (
        <View style={s.hint} pointerEvents="none">
          <Text style={s.hintText}>Zoom in to see ranked intersections</Text>
        </View>
      )}

      <Pressable
        style={[s.fab, { bottom: selected ? "64%" : 32 + insets.bottom }]}
        onPress={goToMe}
        accessibilityLabel="Find intersections near me"
      >
        <Text style={s.fabText}>◎</Text>
      </Pressable>

      <DetailSheet site={selected} onClose={() => setSelected(null)} />
    </View>
  );
}

// Matches the web dashboard's dark basemap. react-native-maps hands this to the
// Google SDK on both platforms.
const DARK_MAP_STYLE = [
  { elementType: "geometry", stylers: [{ color: "#1d2c4d" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#8ec3b9" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#1a3646" }] },
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#304a7d" }] },
  { featureType: "road", elementType: "labels.text.fill", stylers: [{ color: "#98a5be" }] },
  { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#2c6675" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#0e1626" }] },
];

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  center: {
    flex: 1, alignItems: "center", justifyContent: "center",
    backgroundColor: colors.bg, padding: 32, gap: 12,
  },
  centerText: { color: colors.textMuted, fontSize: 13, textAlign: "center" },
  errorTitle: { color: "#f87171", fontSize: 15, fontWeight: "600" },
  retry: {
    marginTop: 8, backgroundColor: colors.accent, borderRadius: 8,
    paddingHorizontal: 20, paddingVertical: 10,
  },
  retryText: { color: "#fff", fontWeight: "600", fontSize: 13 },
  dot: { width: 14, height: 14, borderRadius: 7 },
  topBar: {
    position: "absolute", top: 0, left: 0, right: 0,
    paddingHorizontal: 14, paddingBottom: 10,
    backgroundColor: "rgba(2,6,23,0.92)",
    borderBottomWidth: 1, borderColor: colors.border,
  },
  title: { color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: 10 },
  chips: { flexDirection: "row", gap: 8 },
  chip: {
    flex: 1, alignItems: "center", paddingVertical: 8, borderRadius: 8,
    backgroundColor: colors.surfaceAlt, borderWidth: 1, borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.textMuted, fontSize: 12, fontWeight: "600" },
  chipTextActive: { color: "#fff" },
  hint: {
    position: "absolute", alignSelf: "center", top: "48%",
    backgroundColor: "rgba(2,6,23,0.85)", borderRadius: 999,
    paddingHorizontal: 16, paddingVertical: 9,
    borderWidth: 1, borderColor: colors.border,
  },
  hintText: { color: colors.textMuted, fontSize: 12 },
  fab: {
    position: "absolute", right: 18, width: 48, height: 48, borderRadius: 24,
    alignItems: "center", justifyContent: "center",
    backgroundColor: colors.surfaceAlt, borderWidth: 1, borderColor: colors.border,
  },
  fabText: { color: colors.accent, fontSize: 22 },
});
