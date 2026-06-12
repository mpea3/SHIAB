/**
 * SHIAB Dashboard - Widget management, popout, toasts, and edit mode
 */

(function () {
    "use strict";

    // ============================================================================
    // GLOBAL STATE
    // ============================================================================

    var state = {
        editMode: false,
        draggedWidget: null,
        allModules: [],
        refreshTimers: {},
        lastUpdated: {},
    };

    // Widget updater functions keyed by module name
    var widgetUpdaters = {
        timedate: function (body, data) {
            var timeEl = body.querySelector(".timedate-time");
            var dateEl = body.querySelector(".timedate-date");
            if (timeEl) timeEl.textContent = data.time;
            if (dateEl) dateEl.textContent = data.date;
        },

        weather: function (body, data) {
            if (data.error) {
                body.innerHTML = '<div class="widget-error">' + escapeHtml(data.error_message) + "</div>";
                return;
            }
            var tempEl = body.querySelector(".weather-temp");
            var descEl = body.querySelector(".weather-desc");
            var humidityEl = body.querySelector(".weather-humidity");
            var windEl = body.querySelector(".weather-wind");
            if (tempEl) tempEl.textContent = Math.round(data.temperature);
            if (descEl) descEl.textContent = data.description;
            if (humidityEl) humidityEl.textContent = data.humidity + "%";
            if (windEl) windEl.textContent = data.wind_speed + " " + (data.units === "metric" ? "m/s" : "mph");
        },

        calendar: function (body, data) {
            var listEl = body.querySelector(".calendar-list");
            if (!listEl) return;
            if (!data.upcoming_events || data.upcoming_events.length === 0) {
                listEl.innerHTML =
                    '<li class="widget-list-item"><span class="widget-list-item-name" style="color:var(--color-text-muted)">No upcoming events</span></li>';
                return;
            }
            listEl.innerHTML = data.upcoming_events
                .map(function (event) {
                    var date = new Date(event.start_time);
                    var dateStr = date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
                    var timeStr = event.all_day ? "All day" : date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
                    return (
                        '<li class="widget-list-item">' +
                        '<span class="widget-list-item-name">' + escapeHtml(event.title) + "</span>" +
                        '<span class="widget-list-item-meta">' + dateStr + " " + timeStr + "</span>" +
                        "</li>"
                    );
                })
                .join("");
        },

        bluetooth: function (body, data) {
            var listEl = body.querySelector(".bluetooth-list");
            if (!listEl) return;
            if (!data.devices || data.devices.length === 0) {
                listEl.innerHTML =
                    '<li class="widget-list-item"><span class="widget-list-item-name" style="color:var(--color-text-muted)">No devices found</span></li>';
                return;
            }
            listEl.innerHTML = data.devices
                .map(function (device) {
                    var signal = getSignalBars(device.rssi);
                    return (
                        '<li class="widget-list-item">' +
                        '<span class="widget-list-item-name">' + escapeHtml(device.name || "Unknown") + "</span>" +
                        '<span class="widget-list-item-meta">' + signal + " " + device.rssi + " dBm</span>" +
                        "</li>"
                    );
                })
                .join("");
        },

        wifi: function (body, data) {
            var listEl = body.querySelector(".wifi-list");
            if (!listEl) return;
            if (!data.devices || data.devices.length === 0) {
                listEl.innerHTML =
                    '<li class="widget-list-item"><span class="widget-list-item-name" style="color:var(--color-text-muted)">No devices configured</span></li>';
                return;
            }
            listEl.innerHTML = data.devices
                .map(function (device) {
                    var statusClass = device.online ? "status-online" : "status-offline";
                    var latency = device.online ? device.latency_ms + "ms" : "Offline";
                    return (
                        '<li class="widget-list-item">' +
                        '<div><span class="status-dot ' + statusClass + '"></span> ' +
                        '<span class="widget-list-item-name">' + escapeHtml(device.name) + "</span></div>" +
                        '<span class="widget-list-item-meta">' + device.ip + " - " + latency + "</span>" +
                        "</li>"
                    );
                })
                .join("");
        },

        system_stats: function (body, data) {
            if (data.error) return;
            var stats = { cpu_percent: data.cpu_percent, ram_percent: data.ram_percent, disk_percent: data.disk_percent };
            Object.keys(stats).forEach(function (key) {
                var el = body.querySelector('[data-stat="' + key + '"]');
                if (el) el.textContent = stats[key] + "%";
                var bar = body.querySelector('.stat-row:has([data-stat="' + key + '"]) .stat-bar-fill');
                if (bar) bar.style.width = Math.min(stats[key], 100) + "%";
            });
            var ramDetail = body.querySelector('[data-stat="ram_detail"]');
            if (ramDetail) ramDetail.textContent = data.ram_used_gb + " / " + data.ram_total_gb + " GB";
            var diskDetail = body.querySelector('[data-stat="disk_detail"]');
            if (diskDetail) diskDetail.textContent = data.disk_used_gb + " / " + data.disk_total_gb + " GB";
            var cpuFreq = body.querySelector('[data-stat="cpu_freq"]');
            if (cpuFreq && data.cpu_freq_mhz) cpuFreq.textContent = data.cpu_freq_mhz + " MHz";
            var netRecv = body.querySelector('[data-stat="net_recv"]');
            if (netRecv) netRecv.textContent = data.net_bytes_recv_mb + " MB";
            var netSent = body.querySelector('[data-stat="net_sent"]');
            if (netSent) netSent.textContent = data.net_bytes_sent_mb + " MB";
        },
    };

    // ============================================================================
    // UTILITIES
    // ============================================================================

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    }

    function getSignalBars(rssi) {
        if (rssi >= -50) return "▓▓▓▓";
        if (rssi >= -60) return "▓▓▓░";
        if (rssi >= -70) return "▓▓░░";
        return "▓░░░";
    }

    function timeAgo(ts) {
        var diff = Math.floor((Date.now() - ts) / 1000);
        if (diff < 5) return "Just now";
        if (diff < 60) return diff + "s ago";
        if (diff < 3600) return Math.floor(diff / 60) + "m ago";
        return Math.floor(diff / 3600) + "h ago";
    }

    // ============================================================================
    // TOAST NOTIFICATIONS
    // ============================================================================

    function showToast(message, level, duration) {
        level = level || "info";
        duration = duration || 4000;

        var container = document.getElementById("toast-container");
        if (!container) return;

        var toast = document.createElement("div");
        toast.className = "toast toast-" + level;

        var icons = { info: "ℹ", success: "✓", warning: "⚠", error: "✕" };
        toast.innerHTML =
            '<span class="toast-icon">' + (icons[level] || icons.info) + "</span>" +
            '<span class="toast-message">' + escapeHtml(message) + "</span>" +
            '<button class="toast-dismiss" aria-label="Dismiss">×</button>';

        container.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(function () {
            toast.classList.add("toast-visible");
        });

        var dismissBtn = toast.querySelector(".toast-dismiss");
        dismissBtn.addEventListener("click", function () { removeToast(toast); });

        setTimeout(function () { removeToast(toast); }, duration);
    }

    function removeToast(toast) {
        if (toast.classList.contains("toast-removing")) return;
        toast.classList.add("toast-removing");
        toast.classList.remove("toast-visible");
        setTimeout(function () {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
    }

    // Expose globally for other scripts
    window.showToast = showToast;

    // ============================================================================
    // WIDGET REFRESH
    // ============================================================================

    function refreshWidget(moduleName, card) {
        if (!card) card = document.querySelector('[data-module="' + moduleName + '"]');
        if (!card) return Promise.resolve();

        var body = card.querySelector(".widget-body");
        var refreshBtn = card.querySelector(".widget-refresh-btn");

        // Add loading state
        if (refreshBtn) refreshBtn.classList.add("spinning");
        body.classList.add("widget-loading");

        return fetch("/api/modules/" + moduleName + "/data")
            .then(function (resp) { return resp.json(); })
            .then(function (data) {
                if (widgetUpdaters[moduleName]) {
                    widgetUpdaters[moduleName](body, data);
                }
                state.lastUpdated[moduleName] = Date.now();
                updateLastUpdatedLabel(moduleName);
            })
            .catch(function () {
                showToast("Failed to refresh " + moduleName, "error");
            })
            .finally(function () {
                if (refreshBtn) refreshBtn.classList.remove("spinning");
                body.classList.remove("widget-loading");
            });
    }

    function refreshAllWidgets() {
        var btn = document.getElementById("refresh-all-btn");
        if (btn) {
            btn.classList.add("btn-loading");
            btn.disabled = true;
        }

        var cards = document.querySelectorAll(".widget-card[data-module]");
        var promises = [];
        cards.forEach(function (card) {
            var moduleName = card.dataset.module;
            if (moduleName === "timedate") return;
            promises.push(refreshWidget(moduleName, card));
        });

        Promise.all(promises).then(function () {
            showToast("All widgets refreshed", "success", 2000);
        }).finally(function () {
            if (btn) {
                btn.classList.remove("btn-loading");
                btn.disabled = false;
            }
        });
    }

    function updateLastUpdatedLabel(moduleName) {
        var label = document.querySelector('.widget-last-updated[data-module="' + moduleName + '"]');
        if (!label || !state.lastUpdated[moduleName]) return;
        label.textContent = timeAgo(state.lastUpdated[moduleName]);
    }

    function tickLastUpdated() {
        Object.keys(state.lastUpdated).forEach(updateLastUpdatedLabel);
    }

    // ============================================================================
    // WIDGET POPOUT MODAL
    // ============================================================================

    function openPopout(moduleName) {
        var card = document.querySelector('[data-module="' + moduleName + '"]');
        if (!card) return;

        var overlay = document.getElementById("popout-overlay");
        var modal = document.getElementById("popout-modal");
        var iconEl = document.getElementById("popout-icon");
        var nameEl = document.getElementById("popout-name");
        var contentEl = document.getElementById("popout-content");
        var infoList = document.getElementById("popout-info-list");

        // Copy widget content
        var body = card.querySelector(".widget-body");
        contentEl.innerHTML = body.innerHTML;

        // Set header
        var headerIcon = card.querySelector(".widget-icon");
        var headerName = card.querySelector(".widget-header h2");
        iconEl.innerHTML = headerIcon ? headerIcon.innerHTML : "";
        nameEl.textContent = headerName ? headerName.textContent : moduleName;

        // Populate info sidebar
        var module = state.allModules.find(function (m) { return m.name === moduleName; });
        var lastUpdate = state.lastUpdated[moduleName] ? timeAgo(state.lastUpdated[moduleName]) : "Just now";
        infoList.innerHTML =
            '<div class="popout-info-item"><span class="popout-info-label">Module</span><span class="popout-info-value"><code>' + escapeHtml(moduleName) + '</code></span></div>' +
            '<div class="popout-info-item"><span class="popout-info-label">Size</span><span class="popout-info-value">' + (card.dataset.widgetSize || "medium") + '</span></div>' +
            '<div class="popout-info-item"><span class="popout-info-label">Refresh</span><span class="popout-info-value">' + (card.dataset.refreshInterval || "60") + 's</span></div>' +
            '<div class="popout-info-item"><span class="popout-info-label">Last Updated</span><span class="popout-info-value">' + lastUpdate + '</span></div>';

        // Show modal
        overlay.classList.add("active");
        modal.dataset.module = moduleName;
        document.body.style.overflow = "hidden";

        // Setup popout refresh button
        var refreshBtn = document.getElementById("popout-refresh-btn");
        refreshBtn.onclick = function () {
            refreshBtn.classList.add("spinning");
            fetch("/api/modules/" + moduleName + "/data")
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (widgetUpdaters[moduleName]) {
                        // Update both popout and original widget
                        widgetUpdaters[moduleName](contentEl, data);
                        var origBody = card.querySelector(".widget-body");
                        if (origBody) widgetUpdaters[moduleName](origBody, data);
                    }
                    state.lastUpdated[moduleName] = Date.now();
                })
                .catch(function () { showToast("Refresh failed", "error"); })
                .finally(function () { refreshBtn.classList.remove("spinning"); });
        };
    }

    function closePopout() {
        var overlay = document.getElementById("popout-overlay");
        overlay.classList.remove("active");
        document.body.style.overflow = "";
    }

    // ============================================================================
    // EDIT MODE - DRAG AND DROP
    // ============================================================================

    function setupDragAndDrop() {
        var grid = document.getElementById("dashboard-grid");
        if (!grid) return;

        grid.querySelectorAll(".widget-card").forEach(function (card) {
            if (card.dataset.dragSetup) return;
            card.dataset.dragSetup = "true";

            card.addEventListener("dragstart", handleDragStart);
            card.addEventListener("dragend", handleDragEnd);
            card.addEventListener("dragover", handleDragOver);
            card.addEventListener("drop", handleDrop);
        });
    }

    function handleDragStart(e) {
        if (!state.editMode) { e.preventDefault(); return; }
        state.draggedWidget = this;
        this.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
    }

    function handleDragEnd() {
        this.classList.remove("dragging");
        document.querySelectorAll(".widget-card.drop-target").forEach(function (card) {
            card.classList.remove("drop-target");
        });
        state.draggedWidget = null;
    }

    function handleDragOver(e) {
        if (!state.editMode || !state.draggedWidget) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";

        if (this !== state.draggedWidget) {
            document.querySelectorAll(".widget-card.drop-target").forEach(function (card) {
                card.classList.remove("drop-target");
            });
            this.classList.add("drop-target");

            var grid = this.parentNode;
            var allCards = Array.from(grid.children);
            var draggedIdx = allCards.indexOf(state.draggedWidget);
            var targetIdx = allCards.indexOf(this);

            if (draggedIdx < targetIdx) {
                grid.insertBefore(state.draggedWidget, this.nextSibling);
            } else {
                grid.insertBefore(state.draggedWidget, this);
            }
        }
    }

    function handleDrop(e) {
        e.preventDefault();
        this.classList.remove("drop-target");
        return false;
    }

    // ============================================================================
    // EDIT MODE - SIZE CONTROLS
    // ============================================================================

    function setupSizeControls() {
        var grid = document.getElementById("dashboard-grid");
        if (!grid) return;

        grid.querySelectorAll(".widget-card").forEach(function (card) {
            if (card.dataset.sizeSetup) return;
            card.dataset.sizeSetup = "true";

            var controls = card.querySelector(".widget-edit-controls");
            if (!controls) return;

            controls.querySelectorAll("[data-size]").forEach(function (btn) {
                btn.addEventListener("click", function (e) {
                    e.stopPropagation();
                    updateWidgetSize(card, this.dataset.size);
                });
            });

            var removeBtn = controls.querySelector(".widget-remove");
            if (removeBtn) {
                removeBtn.addEventListener("click", function (e) {
                    e.stopPropagation();
                    card.classList.add("widget-removing");
                    setTimeout(function () { card.remove(); }, 300);
                });
            }
        });
    }

    function updateWidgetSize(card, size) {
        card.classList.remove("widget-small", "widget-medium", "widget-large");
        card.classList.add("widget-" + size);
        card.dataset.widgetSize = size;

        var controls = card.querySelector(".widget-edit-controls");
        if (controls) {
            controls.querySelectorAll("[data-size]").forEach(function (btn) {
                btn.classList.toggle("active", btn.dataset.size === size);
            });
        }
    }

    // ============================================================================
    // EDIT MODE - TOGGLE
    // ============================================================================

    function enterEditMode() {
        state.editMode = true;

        var grid = document.getElementById("dashboard-grid");
        var sidebar = document.getElementById("edit-sidebar");
        var overlay = document.getElementById("edit-overlay");
        var btn = document.getElementById("edit-mode-btn");

        if (!grid || !sidebar || !overlay || !btn) return;

        document.body.classList.add("editing");
        grid.classList.add("edit-mode");
        sidebar.classList.add("active");
        overlay.classList.add("active");
        btn.innerHTML = '<span class="edit-icon">✓</span> Done';
        btn.classList.add("btn-primary");
        btn.classList.remove("btn-secondary");

        grid.querySelectorAll(".widget-card").forEach(function (card) {
            card.classList.add("edit-mode");
            card.draggable = true;
        });

        setupDragAndDrop();
        setupSizeControls();
        populateAvailableModules();
    }

    function exitEditMode() {
        state.editMode = false;

        var grid = document.getElementById("dashboard-grid");
        var sidebar = document.getElementById("edit-sidebar");
        var overlay = document.getElementById("edit-overlay");
        var btn = document.getElementById("edit-mode-btn");

        if (!grid || !sidebar || !overlay || !btn) return;

        document.body.classList.remove("editing");
        grid.classList.remove("edit-mode");
        sidebar.classList.remove("active");
        overlay.classList.remove("active");
        btn.innerHTML = '<span class="edit-icon">✎</span> Edit Layout';
        btn.classList.remove("btn-primary");
        btn.classList.add("btn-secondary");

        grid.querySelectorAll(".widget-card").forEach(function (card) {
            card.classList.remove("edit-mode");
            card.draggable = false;
        });
    }

    function toggleEditMode() {
        if (state.editMode) { exitEditMode(); } else { enterEditMode(); }
    }

    // ============================================================================
    // SIDEBAR - POPULATE MODULES
    // ============================================================================

    function populateAvailableModules() {
        var grid = document.getElementById("dashboard-grid");
        if (!grid) return;

        var currentModules = new Set();
        grid.querySelectorAll("[data-module]").forEach(function (card) {
            currentModules.add(card.dataset.module);
        });

        var list = document.getElementById("available-modules-list");
        if (!list) return;

        list.innerHTML = state.allModules
            .map(function (module) {
                var isOnGrid = currentModules.has(module.name);
                return (
                    '<div class="module-item' + (isOnGrid ? " on-grid" : "") + '" data-module="' + escapeHtml(module.name) + '">' +
                    '<h4>' + module.icon + ' ' + escapeHtml(module.display_name) + '</h4>' +
                    '<p>' + escapeHtml(module.description) + '</p>' +
                    (isOnGrid ? '<span class="module-item-badge">Already on dashboard</span>' : '') +
                    '</div>'
                );
            })
            .join("");

        list.querySelectorAll(".module-item:not(.on-grid)").forEach(function (item) {
            item.addEventListener("click", function () {
                addModuleToGrid(this.dataset.module);
            });
        });
    }

    function addModuleToGrid(moduleName) {
        var grid = document.getElementById("dashboard-grid");
        if (!grid) return;

        var module = state.allModules.find(function (m) { return m.name === moduleName; });
        if (!module) return;

        var card = document.createElement("div");
        card.className = "widget-card widget-" + module.widget_size + " edit-mode";
        card.dataset.module = moduleName;
        card.dataset.widgetSize = module.widget_size;
        card.innerHTML =
            '<div class="widget-edit-controls">' +
                '<button class="widget-btn' + (module.widget_size === 'small' ? ' active' : '') + '" title="Small" data-size="small">S</button>' +
                '<button class="widget-btn' + (module.widget_size === 'medium' ? ' active' : '') + '" title="Medium" data-size="medium">M</button>' +
                '<button class="widget-btn' + (module.widget_size === 'large' ? ' active' : '') + '" title="Large" data-size="large">L</button>' +
                '<button class="widget-btn widget-remove" title="Remove">&times;</button>' +
            '</div>' +
            '<div class="widget-header">' +
                '<span class="widget-icon">' + module.icon + '</span>' +
                '<h2>' + escapeHtml(module.display_name) + '</h2>' +
                '<div class="widget-header-actions">' +
                    '<button class="widget-action-btn widget-refresh-btn" title="Refresh">↻</button>' +
                    '<button class="widget-action-btn widget-expand-btn" title="Expand">⤢</button>' +
                '</div>' +
                '<span class="widget-drag-handle" title="Drag to reorder">&#8942;&#8942;</span>' +
            '</div>' +
            '<div class="widget-body">' +
                '<p style="color:var(--color-text-muted);text-align:center">Module added. Save to apply.</p>' +
            '</div>' +
            '<div class="widget-footer">' +
                '<span class="widget-last-updated" data-module="' + escapeHtml(moduleName) + '">--</span>' +
            '</div>';

        card.draggable = true;
        grid.appendChild(card);

        setupDragAndDrop();
        setupSizeControls();
        setupWidgetActions();
        populateAvailableModules();
        showToast(module.display_name + " added to dashboard", "success", 2000);
    }

    // ============================================================================
    // SIDEBAR - SAVE/RESET
    // ============================================================================

    function saveLayout() {
        var grid = document.getElementById("dashboard-grid");
        if (!grid) return;

        var saveBtn = document.getElementById("save-layout-btn");
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = "Saving...";
        }

        var layout = [];
        grid.querySelectorAll(".widget-card").forEach(function (card) {
            layout.push({ module: card.dataset.module, size: card.dataset.widgetSize || "medium" });
        });

        fetch("/api/dashboard/layout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ layout: layout }),
        }).then(function () {
            exitEditMode();
            showToast("Layout saved", "success", 2000);
            location.reload();
        }).catch(function () {
            showToast("Failed to save layout", "error");
            if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Save Layout"; }
        });
    }

    function resetLayout() {
        if (!confirm("Reset dashboard to default layout?")) return;

        fetch("/api/dashboard/layout", { method: "DELETE" }).then(function () {
            showToast("Layout reset to default", "info", 2000);
            location.reload();
        });
    }

    // ============================================================================
    // CLOCK (time/date widget + status bar clock)
    // ============================================================================

    function startClock() {
        var card = document.querySelector('[data-module="timedate"]');
        var statusClock = document.getElementById("status-bar-clock");

        var tz = "UTC";
        var is24h = false;
        if (card) {
            tz = card.dataset.timezone || "UTC";
            is24h = card.dataset.format24h === "true";
        }

        function tick() {
            var now = new Date();
            var timeOpts = { timeZone: tz, hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: !is24h };

            if (card) {
                var body = card.querySelector(".widget-body");
                var timeEl = body ? body.querySelector(".timedate-time") : null;
                var dateEl = body ? body.querySelector(".timedate-date") : null;
                if (timeEl) timeEl.textContent = now.toLocaleTimeString(undefined, timeOpts);
                if (dateEl) {
                    var dateOpts = { timeZone: tz, weekday: "long", year: "numeric", month: "long", day: "numeric" };
                    dateEl.textContent = now.toLocaleDateString(undefined, dateOpts);
                }
            }

            // Status bar clock (always show HH:MM)
            if (statusClock) {
                var shortOpts = { timeZone: tz, hour: "2-digit", minute: "2-digit", hour12: !is24h };
                statusClock.textContent = now.toLocaleTimeString(undefined, shortOpts);
            }
        }

        tick();
        setInterval(tick, 1000);
    }

    // ============================================================================
    // AUTO-REFRESH
    // ============================================================================

    function startAutoRefresh() {
        document.querySelectorAll(".widget-card[data-module]").forEach(function (card) {
            var moduleName = card.dataset.module;

            if (moduleName === "timedate") return;

            state.lastUpdated[moduleName] = Date.now();
        });
    }

    // ============================================================================
    // WIDGET HEADER ACTIONS (refresh + expand)
    // ============================================================================

    function setupWidgetActions() {
        // Per-widget refresh buttons
        document.querySelectorAll(".widget-refresh-btn").forEach(function (btn) {
            if (btn.dataset.actionSetup) return;
            btn.dataset.actionSetup = "true";

            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                var moduleName = this.dataset.module || this.closest("[data-module]").dataset.module;
                if (moduleName === "timedate") return;
                refreshWidget(moduleName);
            });
        });

        // Per-widget expand buttons
        document.querySelectorAll(".widget-expand-btn").forEach(function (btn) {
            if (btn.dataset.actionSetup) return;
            btn.dataset.actionSetup = "true";

            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                var moduleName = this.dataset.module || this.closest("[data-module]").dataset.module;
                openPopout(moduleName);
            });
        });
    }

    // ============================================================================
    // WEBSOCKET TOAST INTEGRATION
    // ============================================================================

    function setupWSToasts() {
        var proto = location.protocol === "https:" ? "wss" : "ws";
        var ws;

        function connect() {
            try {
                ws = new WebSocket(proto + "://" + location.host + "/ws");
            } catch (_) {
                return;
            }

            ws.onmessage = function (e) {
                try {
                    var msg = JSON.parse(e.data);
                    if (msg.type === "notification") {
                        showToast(msg.title || msg.message || "New notification", msg.level || "info");
                    }
                    if (msg.type === "module_update" && msg.module) {
                        var card = document.querySelector('[data-module="' + msg.module + '"]');
                        if (card && widgetUpdaters[msg.module] && msg.data) {
                            widgetUpdaters[msg.module](card.querySelector(".widget-body"), msg.data);
                            state.lastUpdated[msg.module] = Date.now();
                        }
                    }
                } catch (_) {}
            };

            ws.onclose = function () { setTimeout(connect, 5000); };
            ws.onerror = function () { ws.close(); };
        }

        connect();
    }

    // ============================================================================
    // KEYBOARD SHORTCUTS
    // ============================================================================

    function setupKeyboardShortcuts() {
        document.addEventListener("keydown", function (e) {
            // Escape to close popout or exit edit mode
            if (e.key === "Escape") {
                var popout = document.getElementById("popout-overlay");
                if (popout && popout.classList.contains("active")) {
                    closePopout();
                    return;
                }
                if (state.editMode) {
                    exitEditMode();
                    return;
                }
            }

            // R to refresh all (when not in an input)
            if (e.key === "r" && !e.ctrlKey && !e.metaKey && !e.altKey) {
                var tag = document.activeElement.tagName;
                if (tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
                    e.preventDefault();
                    refreshAllWidgets();
                }
            }

            // E to toggle edit mode
            if (e.key === "e" && !e.ctrlKey && !e.metaKey && !e.altKey) {
                var tag2 = document.activeElement.tagName;
                if (tag2 !== "INPUT" && tag2 !== "TEXTAREA" && tag2 !== "SELECT") {
                    e.preventDefault();
                    toggleEditMode();
                }
            }
        });
    }

    // ============================================================================
    // INITIALIZATION
    // ============================================================================

    document.addEventListener("DOMContentLoaded", function () {
        var grid = document.getElementById("dashboard-grid");
        if (grid) {
            grid.querySelectorAll("[data-module]").forEach(function (card) {
                var iconEl = card.querySelector(".widget-icon");
                var nameEl = card.querySelector(".widget-header h2");
                var module = {
                    name: card.dataset.module,
                    display_name: nameEl ? nameEl.textContent : card.dataset.module,
                    description: "Smart home module",
                    icon: iconEl ? iconEl.innerHTML : "",
                    widget_size: card.dataset.widgetSize || "medium",
                };
                if (!state.allModules.find(function (m) { return m.name === module.name; })) {
                    state.allModules.push(module);
                }
                card.draggable = false;
            });
        }

        // Also fetch full module list from API for sidebar
        fetch("/api/modules")
            .then(function (r) { return r.json(); })
            .then(function (modules) {
                modules.forEach(function (m) {
                    if (!state.allModules.find(function (e) { return e.name === m.name; })) {
                        state.allModules.push(m);
                    }
                });
            })
            .catch(function () {});

        // Edit mode toggle
        var editBtn = document.getElementById("edit-mode-btn");
        if (editBtn) editBtn.addEventListener("click", function (e) { e.preventDefault(); toggleEditMode(); });

        // Sidebar close
        var sidebarClose = document.getElementById("sidebar-close");
        if (sidebarClose) sidebarClose.addEventListener("click", function (e) { e.preventDefault(); exitEditMode(); });

        // Overlay click closes edit mode
        var overlay = document.getElementById("edit-overlay");
        if (overlay) overlay.addEventListener("click", exitEditMode);

        // Save and reset
        var saveBtn = document.getElementById("save-layout-btn");
        if (saveBtn) saveBtn.addEventListener("click", saveLayout);

        var resetBtn = document.getElementById("reset-layout-btn");
        if (resetBtn) resetBtn.addEventListener("click", resetLayout);

        // Refresh all
        var refreshAllBtn = document.getElementById("refresh-all-btn");
        if (refreshAllBtn) refreshAllBtn.addEventListener("click", refreshAllWidgets);

        // Popout modal close
        var popoutClose = document.getElementById("popout-close-btn");
        if (popoutClose) popoutClose.addEventListener("click", closePopout);

        var popoutOverlay = document.getElementById("popout-overlay");
        if (popoutOverlay) {
            popoutOverlay.addEventListener("click", function (e) {
                if (e.target === popoutOverlay) closePopout();
            });
        }

        // Setup per-widget actions
        setupWidgetActions();

        // Start clocks and auto-refresh
        startClock();
        startAutoRefresh();
        setupWSToasts();
        setupKeyboardShortcuts();

        // Tick "last updated" labels every 15s
        setInterval(tickLastUpdated, 15000);
    });
})();
