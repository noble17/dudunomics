export function ThemeScript() {
  const code = `
(() => {
  const storageKey = "dudunomics-theme";

  const getStoredTheme = () => {
    try {
      const stored = window.localStorage.getItem(storageKey);
      return stored === "light" || stored === "dark" ? stored : null;
    } catch {
      return null;
    }
  };

  const applyTheme = (theme, persist = false) => {
    document.documentElement.classList.toggle("light", theme === "light");
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
    if (persist) {
      try {
        window.localStorage.setItem(storageKey, theme);
      } catch {}
    }
  };

  const toggleTheme = () => {
    const next = document.documentElement.classList.contains("light") ? "dark" : "light";
    applyTheme(next, true);
  };

  const bindToggleButtons = () => {
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      if (button.__dudunomicsThemeBound) return;
      button.__dudunomicsThemeBound = true;
      button.addEventListener("click", toggleTheme);
    });
  };

  try {
    const stored = getStoredTheme();
    const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
    applyTheme(stored ?? (prefersLight ? "light" : "dark"));
  } catch {
    document.documentElement.classList.add("dark");
    document.documentElement.style.colorScheme = "dark";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      bindToggleButtons();
    });
  } else {
    bindToggleButtons();
  }

  setTimeout(bindToggleButtons, 0);
})();
`;

  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}
