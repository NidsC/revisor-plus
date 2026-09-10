(() => {
  const root = document.getElementById("schoolOnboarding");
  if (!root || root.dataset.initialised === "1") return;
  root.dataset.initialised = "1";

  const searchUrl = root.dataset.searchUrl;
  const saveUrl = root.dataset.saveUrl;
  const skipUrl = root.dataset.skipUrl;
  const nextUrl = root.dataset.nextUrl || "/";

  const nameForm = document.getElementById("nameSearchForm");
  const postcodeForm = document.getElementById("postcodeSearchForm");
  const nameInput = document.getElementById("schoolSearch");
  const postcodeInput = document.getElementById("postcodeSearch");
  const resultsWrap = document.getElementById("schoolResults");
  const resultsSubtitle = document.getElementById("resultsSubtitle");
  const resultsCount = document.getElementById("resultsCount");
  const loadingState = document.getElementById("loadingState");
  const emptyState = document.getElementById("emptyState");
  const errorState = document.getElementById("errorState");
  const selectedWrap = document.getElementById("selectedSchools");
  const selectedEmpty = document.getElementById("selectedEmpty");
  const selectedCount = document.getElementById("selectedCount");
  const continueButton = document.getElementById("continueButton");
  const skipButton = document.getElementById("skipButton");
  const saveMessage = document.getElementById("saveMessage");
  const fitMapButton = document.getElementById("fitMapButton");
  const mapFallback = document.getElementById("mapFallback");

  let initialSchools = [];
  try {
    initialSchools = JSON.parse(document.getElementById("initialSchools")?.textContent || "[]");
  } catch (_) {
    initialSchools = [];
  }

  const selected = new Map(initialSchools.map((school) => [Number(school.id), school]));
  let currentResults = [];
  let currentCentre = null;
  let activeMode = "name";
  let requestController = null;
  let debounceTimer = null;

  let map = null;
  let markerLayer = null;
  let homeMarker = null;
  const markerBySchoolId = new Map();

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function initMap() {
    if (!window.L) {
      document.getElementById("schoolMap").classList.add("is-hidden");
      mapFallback.classList.remove("is-hidden");
      return;
    }

    map = L.map("schoolMap", { zoomControl: true, scrollWheelZoom: false }).setView([51.5074, -0.1278], 9);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
    renderMap();
  }

  function schoolIcon(isSelected) {
    return L.divIcon({
      className: "",
      html: `<div class="school-marker${isSelected ? " is-selected" : ""}"><span>${isSelected ? "✓" : "+"}</span></div>`,
      iconSize: [34, 34],
      iconAnchor: [17, 30],
      popupAnchor: [0, -28],
    });
  }

  function homeIcon() {
    return L.divIcon({ className: "", html: '<div class="home-marker"></div>', iconSize: [18, 18], iconAnchor: [9, 9] });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function renderMap() {
    if (!map || !markerLayer) return;
    markerLayer.clearLayers();
    markerBySchoolId.clear();
    if (homeMarker) {
      map.removeLayer(homeMarker);
      homeMarker = null;
    }

    const bounds = [];
    currentResults.forEach((school) => {
      if (school.latitude == null || school.longitude == null) return;
      const id = Number(school.id);
      const marker = L.marker([school.latitude, school.longitude], { icon: schoolIcon(selected.has(id)) });
      const addLabel = selected.has(id) ? "Remove school" : "Add school";
      marker.bindPopup(`
        <div class="map-popup-name">${escapeHtml(school.name)}</div>
        <div class="map-popup-meta">${escapeHtml([school.town, school.postcode].filter(Boolean).join(" · "))}</div>
        <button type="button" class="map-popup-button" data-map-school-id="${id}">${addLabel}</button>
      `);
      marker.on("popupopen", (event) => {
        const button = event.popup.getElement()?.querySelector("[data-map-school-id]");
        if (button) button.addEventListener("click", () => toggleSchool(school));
      });
      marker.addTo(markerLayer);
      markerBySchoolId.set(id, marker);
      bounds.push([school.latitude, school.longitude]);
    });

    if (currentCentre?.latitude != null && currentCentre?.longitude != null) {
      homeMarker = L.marker([currentCentre.latitude, currentCentre.longitude], { icon: homeIcon(), zIndexOffset: 1000 })
        .bindTooltip("Your postcode", { direction: "top" })
        .addTo(map);
      bounds.push([currentCentre.latitude, currentCentre.longitude]);
    }

    if (bounds.length) {
      map.fitBounds(bounds, { padding: [34, 34], maxZoom: 13 });
    }
  }

  function renderResults() {
    resultsWrap.innerHTML = "";
    emptyState.classList.toggle("is-hidden", currentResults.length > 0);
    resultsCount.hidden = currentResults.length === 0;
    resultsCount.textContent = `${currentResults.length} result${currentResults.length === 1 ? "" : "s"}`;

    currentResults.forEach((school) => {
      const id = Number(school.id);
      const isSelected = selected.has(id);
      const card = document.createElement("article");
      card.className = `school-card${isSelected ? " is-selected" : ""}`;

      const info = document.createElement("div");
      const metaItems = [school.town, school.postcode, school.type].filter(Boolean);
      if (school.distance_km != null) metaItems.unshift(`${school.distance_km} km away`);
      info.innerHTML = `
        <h3 class="school-name">${escapeHtml(school.name)}</h3>
        <div class="school-meta">
          ${metaItems.map((item, index) => `<span${index === 0 && school.distance_km != null ? ' class="school-distance"' : ""}>${escapeHtml(item)}</span>`).join("")}
        </div>
      `;

      const button = document.createElement("button");
      button.type = "button";
      button.className = `add-school${isSelected ? " is-selected" : ""}`;
      button.textContent = isSelected ? "✓" : "+";
      button.setAttribute("aria-label", `${isSelected ? "Remove" : "Add"} ${school.name}`);
      button.addEventListener("click", () => toggleSchool(school));

      card.append(info, button);
      resultsWrap.appendChild(card);
    });
  }

  function renderSelected() {
    selectedWrap.innerHTML = "";
    const values = Array.from(selected.values());
    selectedEmpty.classList.toggle("is-hidden", values.length > 0);
    selectedCount.textContent = `${values.length} selected`;
    continueButton.disabled = values.length === 0;

    values.forEach((school) => {
      const chip = document.createElement("div");
      chip.className = "selected-chip";
      const label = document.createElement("span");
      label.textContent = school.name;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `Remove ${school.name}`);
      remove.addEventListener("click", () => toggleSchool(school));
      chip.append(label, remove);
      selectedWrap.appendChild(chip);
    });
  }

  function toggleSchool(school) {
    const id = Number(school.id);
    if (selected.has(id)) selected.delete(id);
    else selected.set(id, school);
    saveMessage.textContent = "";
    renderResults();
    renderSelected();
    renderMap();
  }

  function setLoading(isLoading) {
    loadingState.classList.toggle("is-hidden", !isLoading);
    if (isLoading) {
      emptyState.classList.add("is-hidden");
      errorState.classList.add("is-hidden");
      resultsWrap.innerHTML = "";
      resultsCount.hidden = true;
    }
  }

  async function runSearch(params) {
    if (requestController) requestController.abort();
    requestController = new AbortController();
    setLoading(true);
    errorState.classList.add("is-hidden");

    try {
      const url = new URL(searchUrl, window.location.origin);
      Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
      const response = await fetch(url, { signal: requestController.signal, headers: { "X-Requested-With": "XMLHttpRequest" } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "We couldn't find schools right now.");

      currentResults = Array.isArray(data.schools) ? data.schools : [];
      currentCentre = data.centre || null;
      if (data.postcode) postcodeInput.value = data.postcode;

      if (params.postcode) {
        resultsSubtitle.textContent = currentResults.length
          ? `Nearest schools to ${data.postcode || params.postcode}.`
          : `No nearby schools found for ${data.postcode || params.postcode}.`;
      } else {
        resultsSubtitle.textContent = currentResults.length
          ? `Matches for “${params.q}”.`
          : `No schools matched “${params.q}”.`;
      }
      renderResults();
      renderMap();
    } catch (error) {
      if (error.name === "AbortError") return;
      currentResults = [];
      currentCentre = null;
      renderResults();
      renderMap();
      errorState.textContent = error.message || "Something went wrong.";
      errorState.classList.remove("is-hidden");
      emptyState.classList.add("is-hidden");
    } finally {
      setLoading(false);
    }
  }

  document.querySelectorAll(".mode-button").forEach((button) => {
    button.addEventListener("click", () => {
      activeMode = button.dataset.mode;
      document.querySelectorAll(".mode-button").forEach((item) => {
        const active = item === button;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", active ? "true" : "false");
      });
      nameForm.classList.toggle("is-hidden", activeMode !== "name");
      postcodeForm.classList.toggle("is-hidden", activeMode !== "postcode");
      (activeMode === "name" ? nameInput : postcodeInput).focus();
    });
  });

  nameForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const q = nameInput.value.trim();
    if (q.length < 2) {
      errorState.textContent = "Type at least 2 characters of the school name.";
      errorState.classList.remove("is-hidden");
      return;
    }
    runSearch({ q });
  });

  nameInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = nameInput.value.trim();
    if (q.length < 2) return;
    debounceTimer = setTimeout(() => runSearch({ q }), 350);
  });

  postcodeForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const postcode = postcodeInput.value.trim();
    if (!postcode) {
      errorState.textContent = "Enter your postcode first.";
      errorState.classList.remove("is-hidden");
      return;
    }
    runSearch({ postcode });
  });

  fitMapButton.addEventListener("click", renderMap);

  continueButton.addEventListener("click", async () => {
    if (!selected.size) return;
    continueButton.disabled = true;
    saveMessage.textContent = "Saving…";
    try {
      const response = await fetch(saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          school_ids: Array.from(selected.keys()),
          postcode: postcodeInput.value.trim(),
          next: nextUrl,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "We couldn't save your schools.");
      window.location.assign(data.redirect || nextUrl || "/");
    } catch (error) {
      saveMessage.textContent = error.message || "We couldn't save your schools.";
      continueButton.disabled = false;
    }
  });

  skipButton.addEventListener("click", async () => {
    skipButton.disabled = true;
    saveMessage.textContent = "";
    try {
      const response = await fetch(skipUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "We couldn't skip this step.");
      window.location.assign(data.redirect || "/");
    } catch (error) {
      saveMessage.textContent = error.message || "We couldn't skip this step.";
      skipButton.disabled = false;
    }
  });

  renderSelected();
  initMap();
})();
