document.addEventListener("DOMContentLoaded", () => {
    // 1. Swap button behavior
    const swapBtn = document.getElementById("swap-button");
    if (swapBtn) {
        swapBtn.addEventListener("click", () => {
            const start = document.getElementById("start");
            const end = document.getElementById("end");
            if (start && end) {
                const temp = start.value;
                start.value = end.value;
                end.value = temp;
            }
        });
    }

    // 2. Popular route pills behavior
    const pills = document.querySelectorAll(".route-pill");
    pills.forEach(pill => {
        pill.addEventListener("click", () => {
            const startDistrict = pill.getAttribute("data-start");
            const endDistrict = pill.getAttribute("data-end");
            const startSelect = document.getElementById("start");
            const endSelect = document.getElementById("end");
            if (startSelect && endSelect) {
                startSelect.value = startDistrict;
                endSelect.value = endDistrict;
                // Highlight form
                const form = document.getElementById("route-form");
                if (form) {
                    form.classList.add("highlight-flash");
                    setTimeout(() => form.classList.remove("highlight-flash"), 400);
                }
            }
        });
    });

    // 3. Interactive Leaflet Map on result page
    const mapElement = document.getElementById("route-map");
    if (mapElement && typeof L !== "undefined" && window.BYTE_TRIP_DATA) {
        initRouteMap();
    }
});

function initRouteMap() {
    const data = window.BYTE_TRIP_DATA;
    const coordsMap = window.DISTRICT_COORDS || {};

    if (!data || data.same_route) return;

    // Bangladesh center coordinates
    const map = L.map("route-map").setView([23.8103, 90.4125], 7);

    // OpenStreetMap tile layer
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    let activeLayerGroup = L.layerGroup().addTo(map);

    const routeColorMap = {
        "cheapest": "#059669",
        "shortest_distance": "#2563eb",
        "fastest": "#d97706",
        "bfs": "#7c3aed"
    };

    function renderRouteOnMap(routeKey) {
        activeLayerGroup.clearLayers();

        let pathList = [];
        let label = "";

        if (routeKey === "bfs" && data.bfs) {
            pathList = data.bfs.path || [];
            label = "Fewest Legs (BFS)";
        } else if (data.comparison) {
            const found = data.comparison.find(item => item.key === routeKey);
            if (found && found.result) {
                pathList = found.result.path || [];
                label = found.label;
            }
        }

        if (!pathList || pathList.length === 0) return;

        const latLngs = [];
        pathList.forEach((district, index) => {
            const coord = coordsMap[district];
            if (coord && coord.length === 2) {
                const [lat, lng] = coord;
                latLngs.push([lat, lng]);

                // Create custom circle marker
                const isStart = index === 0;
                const isEnd = index === pathList.length - 1;
                const markerColor = isStart ? "#16a34a" : (isEnd ? "#dc2626" : (routeColorMap[routeKey] || "#0f766e"));

                const marker = L.circleMarker([lat, lng], {
                    radius: isStart || isEnd ? 9 : 6,
                    fillColor: markerColor,
                    color: "#ffffff",
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.95
                }).addTo(activeLayerGroup);

                const roleText = isStart ? "Origin" : (isEnd ? "Destination" : `Hop #${index}`);
                marker.bindPopup(`<strong>${district}</strong><br><span style="font-size:0.85em;color:#555;">${roleText} (${label})</span>`);
            }
        });

        if (latLngs.length > 1) {
            const polyline = L.polyline(latLngs, {
                color: routeColorMap[routeKey] || "#0f766e",
                weight: 5,
                opacity: 0.85,
                dashArray: routeKey === "bfs" ? "6, 8" : null
            }).addTo(activeLayerGroup);

            map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
        }
    }

    // Initial render: cheapest or first comparison row
    const initialKey = data.comparison && data.comparison.length > 0 ? data.comparison[0].key : "cheapest";
    renderRouteOnMap(initialKey);

    // Tab buttons event listener
    const tabBtns = document.querySelectorAll(".map-tab-btn");
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const key = btn.getAttribute("data-route-key");
            renderRouteOnMap(key);
        });
    });
}
