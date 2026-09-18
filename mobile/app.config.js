// Dynamic Expo config: pulls the platform Maps SDK keys and the data URL out of
// the environment so no key is ever committed. EAS Build reads them from the
// project's environment variables; locally they come from a .env you create
// from .env.example.

const withEnv = (v, fallback) => process.env[v] ?? fallback;

export default {
  expo: {
    name: "KSI Emergence",
    slug: "ksi-emergence",
    version: "0.1.0",
    orientation: "portrait",
    scheme: "ksi",
    userInterfaceStyle: "dark",
    backgroundColor: "#020617",
    assetBundlePatterns: ["**/*"],
    icon: "./assets/icon.png",

    splash: {
      image: "./assets/splash.png",
      resizeMode: "contain",
      backgroundColor: "#020617",
    },

    ios: {
      bundleIdentifier: "org.ksiemergence.app",
      supportsTablet: true,
      config: {
        googleMapsApiKey: withEnv("GOOGLE_MAPS_IOS_API_KEY"),
      },
      infoPlist: {
        // Only requested when the user taps "near me" -- the app is fully usable
        // without granting it.
        NSLocationWhenInUseUsageDescription:
          "Shows which predicted high-risk intersections are near you.",
        ITSAppUsesNonExemptEncryption: false,
      },
    },

    android: {
      package: "org.ksiemergence.app",
      adaptiveIcon: {
        foregroundImage: "./assets/adaptive-icon.png",
        backgroundColor: "#020617",
      },
      config: {
        googleMaps: {
          apiKey: withEnv("GOOGLE_MAPS_ANDROID_API_KEY"),
        },
      },
      permissions: ["ACCESS_COARSE_LOCATION", "ACCESS_FINE_LOCATION"],
    },

    plugins: [
      [
        "expo-location",
        {
          locationWhenInUsePermission:
            "Shows which predicted high-risk intersections are near you.",
        },
      ],
    ],

    extra: {
      dataBaseUrl: withEnv(
        "DATA_BASE_URL",
        "https://ksi-emergence.onrender.com/data"
      ),
      eas: {
        // Filled in by `eas init`.
        projectId: withEnv("EAS_PROJECT_ID"),
      },
    },
  },
};
