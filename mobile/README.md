# KSI Emergence — mobile app

Android and iOS app for the intersection risk map, built with Expo / React Native
and `react-native-maps` on the Google provider for both platforms.

It reads the **same two data files** the web dashboard serves, over HTTP rather
than bundled into the binary. That is deliberate: a new model export reaches users
on their next app launch instead of requiring an app store release.

**Status: scaffold.** The code is complete and parses, but it has not been run on
a device or simulator — that needs the platform Maps SDK keys below plus a build.
Treat the first `expo run:android` as the real smoke test.

---

## What it does

- Google basemap, dark-styled to match the web dashboard
- Top 50 / 100 / 200 / 500 shortlist toggle
- Tap a site for rank, percentile, council district, crash history, and the top
  SHAP signals
- 76.2 m ring on the selected site — the crash-assignment buffer the features are
  actually built on, so it is visible which crashes belong to that node
- "Near me" button: centres on the user and selects the closest shortlisted site
- Deep links out to Street View, Google Maps, and driving directions

Markers only draw below a zoom threshold (`MARKER_ZOOM_DELTA` in `src/MapScreen.js`)
and are culled to the viewport. Native markers are expensive; 500 at once is
visibly janky on mid-range Android.

---

## Setup

### 1. Platform API keys

These are **separate keys from the web dashboard's**, in the same Google Cloud
project. Android keys are restricted by package name plus SHA-1 signing
certificate; iOS keys by bundle identifier. A browser-restricted key will not work
on either platform.

1. Google Cloud console → **APIs & Services → Library** → enable
   **Maps SDK for Android** and **Maps SDK for iOS**.
2. **Credentials → Create credentials → API key**, once per platform.
3. Restrict each one:
   - Android: *Android apps* → package `org.ksiemergence.app` + your SHA-1.
     Get the debug SHA-1 with `eas credentials`, or for a local debug build:
     `keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android`
   - iOS: *iOS apps* → bundle ID `org.ksiemergence.app`

```bash
cp .env.example .env
```

Fill in `GOOGLE_MAPS_ANDROID_API_KEY`, `GOOGLE_MAPS_IOS_API_KEY`, and
`DATA_BASE_URL` (point it at the deployed dashboard, e.g.
`https://ksi-emergence.onrender.com/data`).

### 2. Install and run

```bash
npm install
npx expo run:android     # needs Android Studio + an emulator or device
npx expo run:ios         # needs a Mac with Xcode
```

`npx expo start` alone is **not** enough. `react-native-maps` contains native code,
so Expo Go cannot run this app — you need a development build, which is what
`expo run:*` produces.

---

## Building for distribution

Uses EAS Build, so an iOS build does not require a Mac.

```bash
npm install -g eas-cli
eas login
eas init                 # writes the projectId

eas build --platform android --profile preview   # installable APK
eas build --platform ios --profile preview       # needs an Apple Developer account
```

Set the API keys as EAS secrets so they are never committed:

```bash
eas secret:create --name GOOGLE_MAPS_ANDROID_API_KEY --value "AIza..."
eas secret:create --name GOOGLE_MAPS_IOS_API_KEY --value "AIza..."
```

Store submission:

```bash
eas build --platform android --profile production
eas submit --platform android
```

Accounts required: Google Play Developer, $25 one-time. Apple Developer Program,
$99/year.

---

## Store review notes

Two things are likely to come up, so prepare for them:

- **Location permission.** Only requested when the user taps "near me", and the app
  is fully usable without it. The usage string is in `app.config.js`. Apple will
  reject a vague one — the current string names the specific feature.
- **Safety-adjacent content.** The app presents *model predictions*, not official
  hazard designations. Make that explicit in the store description and consider an
  in-app disclaimer before submitting. Do not describe it in terms that imply an
  official City of San Diego safety warning; it is independent research.

---

## Structure

```
App.js                  entry; providers only
app.config.js           dynamic Expo config, reads keys from env
eas.json                build profiles
src/
  MapScreen.js          map, markers, filters, viewport culling
  DetailSheet.js        bottom sheet: history, SHAP bars, Google deep links
  useIntersections.js   fetches the dashboard's data files
  theme.js              palette + risk tiers, mirrored from the web dashboard
  lib/format.js         percentile formatting, haversine
assets/                 placeholder icons — replace before store submission
```

The icons in `assets/` are generated placeholders. Replace them with real artwork
before any store submission.
