// Inline script applied before first paint to set the persisted theme (or the
// system preference) on <html>, avoiding a light flash when dark is active.
// Kept as a plain string: it must run synchronously before hydration.
export const themeInitScript = `
try {
  var stored = localStorage.getItem("ketabdaneh-theme");
  var theme = stored === "light" || stored === "dark"
    ? stored
    : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = theme;
} catch (e) {}
`;
