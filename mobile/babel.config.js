module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    // Reanimated's plugin must stay last in the list.
    plugins: ["react-native-reanimated/plugin"],
  };
};
