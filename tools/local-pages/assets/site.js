(() => {
  "use strict";

  const storageKey = "native-agent-pages-theme";
  const choices = ["system", "light", "dark"];
  const root = document.documentElement;
  const systemTheme = typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)")
    : null;
  let preference = "system";
  let themeControl = null;

  const validChoice = (value) => choices.includes(value);

  try {
    const saved = window.localStorage.getItem(storageKey);
    if (validChoice(saved)) preference = saved;
  } catch {
    // File previews and browsers that block storage still retain a usable theme.
  }

  function applyTheme() {
    const effective = preference === "system"
      ? (systemTheme?.matches ? "dark" : "light")
      : preference;
    root.dataset.theme = effective;
    root.dataset.themePreference = preference;
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.content = getComputedStyle(root).getPropertyValue("--canvas").trim();
    }
    if (!themeControl) return;

    if (themeControl.tagName === "SELECT") {
      themeControl.value = preference;
    } else if (themeControl.tagName === "BUTTON") {
      const next = choices[(choices.indexOf(preference) + 1) % choices.length];
      themeControl.textContent = `Theme: ${preference}`;
      themeControl.setAttribute("aria-label", `Theme: ${preference}, currently ${effective}. Activate to use ${next}.`);
    }
  }

  function setTheme(value) {
    preference = validChoice(value) ? value : "system";
    applyTheme();
    try {
      window.localStorage.setItem(storageKey, preference);
    } catch {
      // A storage failure must not prevent the chosen theme from being applied.
    }
  }

  applyTheme();

  if (systemTheme) {
    const onSystemChange = () => {
      if (preference === "system") applyTheme();
    };
    if (typeof systemTheme.addEventListener === "function") {
      systemTheme.addEventListener("change", onSystemChange);
    } else if (typeof systemTheme.addListener === "function") {
      systemTheme.addListener(onSystemChange);
    }
  }

  window.addEventListener("storage", (event) => {
    if (event.key !== storageKey && event.key !== null) return;
    preference = validChoice(event.newValue) ? event.newValue : "system";
    applyTheme();
  });

  function setupTheme() {
    themeControl = document.getElementById("theme-toggle");
    if (!themeControl) return;
    applyTheme();
    if (themeControl.tagName === "SELECT") {
      themeControl.addEventListener("change", () => setTheme(themeControl.value));
    } else if (themeControl.tagName === "BUTTON") {
      themeControl.addEventListener("click", () => {
        setTheme(choices[(choices.indexOf(preference) + 1) % choices.length]);
      });
    }
  }

  function setupGaps() {
    const register = document.getElementById("gap-register");
    const search = document.getElementById("gap-search");
    const group = document.getElementById("gap-group");
    const severity = document.getElementById("gap-severity");
    const count = document.getElementById("gap-result-count");
    const empty = document.getElementById("gap-empty");
    const reset = document.getElementById("gap-reset");
    if (!register || !search || !group || !severity) return;

    const normalize = (value) => String(value ?? "").normalize("NFKC").toLowerCase().trim();
    const isAll = (value) => value === "" || value === "all" || value === "*";
    const entries = Array.from(register.querySelectorAll(".gap-card")).map((card) => ({
      card,
      search: normalize(card.dataset.search || card.textContent),
      group: normalize(card.dataset.group),
      severity: normalize(card.dataset.severity),
    }));

    if (count) {
      count.setAttribute("role", "status");
      count.setAttribute("aria-live", "polite");
      count.setAttribute("aria-atomic", "true");
    }

    function update() {
      const terms = normalize(search.value).split(/\s+/).filter(Boolean);
      const selectedGroup = normalize(group.value);
      const selectedSeverity = normalize(severity.value);
      let visible = 0;

      for (const entry of entries) {
        const matches = terms.every((term) => entry.search.includes(term))
          && (isAll(selectedGroup) || entry.group === selectedGroup)
          && (isAll(selectedSeverity) || entry.severity === selectedSeverity);
        entry.card.hidden = !matches;
        if (matches) visible += 1;
      }

      if (count) count.textContent = `${visible} of ${entries.length} ${entries.length === 1 ? "gap" : "gaps"}`;
      if (empty) empty.hidden = visible !== 0;
    }

    function clearSelect(select) {
      const all = Array.from(select.options).find((option) => isAll(normalize(option.value)));
      select.value = all ? all.value : "";
    }

    // Vercel Web Interface Guidelines: filters belong in shareable URL state.
    // Native URLSearchParams and History keep this static page dependency-free.
    function restoreFilters() {
      const params = new URL(window.location.href).searchParams;
      search.value = params.get("q") || "";
      for (const [key, select] of [["group", group], ["severity", severity]]) {
        const value = normalize(params.get(key));
        const option = Array.from(select.options).find((item) => normalize(item.value) === value);
        if (option) select.value = option.value;
        else clearSelect(select);
      }
      update();
    }

    function writeFilters(push) {
      const url = new URL(window.location.href);
      for (const [key, value] of [["q", search.value], ["group", group.value], ["severity", severity.value]]) {
        if (value && (key === "q" || !isAll(normalize(value)))) url.searchParams.set(key, value);
        else url.searchParams.delete(key);
      }
      if (url.href !== window.location.href) {
        window.history[push ? "pushState" : "replaceState"](window.history.state, "", url.href);
      }
    }

    function filterChanged(push) {
      update();
      writeFilters(push);
    }

    search.addEventListener("input", () => filterChanged(false));
    group.addEventListener("change", () => filterChanged(true));
    severity.addEventListener("change", () => filterChanged(true));
    window.addEventListener("popstate", restoreFilters);
    if (reset) {
      reset.addEventListener("click", (event) => {
        event.preventDefault();
        search.value = "";
        clearSelect(group);
        clearSelect(severity);
        filterChanged(true);
        search.focus();
      });
    }
    if (search.form) {
      search.form.addEventListener("reset", () => window.setTimeout(() => filterChanged(true), 0));
      search.form.addEventListener("submit", (event) => event.preventDefault());
    }
    restoreFilters();
  }

  function setupArchitectureDetails() {
    for (const details of document.querySelectorAll("details[data-layer-src]")) {
      let loading = false;
      details.addEventListener("toggle", async () => {
        if (!details.open || details.dataset.loaded === "true" || loading) return;
        const target = details.querySelector(".architecture-detail-content");
        const source = new URL(details.dataset.layerSrc, document.baseURI);
        if (!target || source.origin !== window.location.origin || !source.pathname.includes("/architecture/layers/")) return;
        loading = true;
        target.setAttribute("aria-busy", "true");
        try {
          const response = await fetch(source.href, { mode: "same-origin", credentials: "omit" });
          if (!response.ok) throw new Error(`Detail page returned HTTP ${response.status}`);
          const parsed = new DOMParser().parseFromString(await response.text(), "text/html");
          const content = parsed.getElementById("architecture-detail-content");
          if (!content) throw new Error("Detail page has no component content");
          target.replaceChildren(...Array.from(content.childNodes, (node) => document.importNode(node, true)));
          details.dataset.loaded = "true";
        } catch (error) {
          const message = document.createElement("p");
          message.textContent = `Details could not be loaded: ${error.message}. Close and expand to retry, or open the detail page.`;
          const link = document.createElement("a");
          link.href = source.href;
          link.textContent = "Open the detail page";
          target.replaceChildren(message, link);
        } finally {
          target.removeAttribute("aria-busy");
          loading = false;
        }
      });
    }
  }

  function setup() {
    setupTheme();
    setupGaps();
    setupArchitectureDetails();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup, { once: true });
  } else {
    setup();
  }
})();
