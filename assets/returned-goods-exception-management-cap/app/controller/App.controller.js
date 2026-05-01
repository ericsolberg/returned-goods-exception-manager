sap.ui.define([
  "sap/ui/core/mvc/Controller",
  "sap/ui/model/json/JSONModel",
  "sap/ui/core/Fragment"
], function (Controller, JSONModel, Fragment) {
  "use strict";

  // Polling interval for backend change-marker detection.
  // NOTE: Smart-polling is used here because this app is deployed to the HTML5
  // Application Repository and launched via the SAP managed approuter, which does
  // not support long-lived push connections (SSE / WebSocket). For a production
  // real-time solution, use a standalone approuter with WebSocket/SSE support, or
  // a proper event/pub-sub design (e.g. SAP Event Mesh or Redis Pub/Sub).
  var POLL_INTERVAL_MS = 5000;

  return Controller.extend("com.tapestry.returnedgoodsexceptionmanagement.controller.App", {

    onInit: function () {
      this.getView().setModel(new JSONModel({ orders: [], matched: [], partial: [], unmatched: [], matchedAmount: 0, partialAmount: 0, unmatchedAmount: 0 }), "list");
      this.getView().setModel(new JSONModel({ order: null, expected: [], received: [], history: [] }), "detail");
      this.getView().setModel(new JSONModel({ msg: "", type: "Information", visible: false }), "banner");
      this.getView().setModel(new JSONModel({ companyCodes: [], distributionCenters: [], customerNames: [] }), "filterOptions");

      Fragment.load({
        id: this.getView().getId(),
        name: "com.tapestry.returnedgoodsexceptionmanagement.fragment.Dialogs",
        controller: this
      }).then(function (dialogs) {
        var oView = this.getView();
        [].concat(dialogs).forEach(function (d) { oView.addDependent(d); });
      }.bind(this));

      this._pollTimer = null;
      this._lastChangeMarker = null; // null = baseline not yet captured by first poll

      this.loadList();
      this._startPolling();
    },

    // ── URL construction ────────────────────────────────────────────────────
    // sap.ui.require.toUrl returns the app's resource base (e.g.
    // ".../comtapestryreturnedgoodsexceptionmanagement" in Work Zone, or
    // "http://localhost:4004" when run locally via index.html).
    // Appending "/exception" gives a URL that stays within the app prefix so
    // xs-app.json routes are applied before forwarding to the destination.

    _svcBase: function () {
      return sap.ui.require.toUrl("com/tapestry/returnedgoodsexceptionmanagement") + "/exception";
    },

    _fetch: async function (path, opts) {
      var res = await fetch(this._svcBase() + path, Object.assign(
        { headers: { "Content-Type": "application/json" } },
        opts,
        { headers: Object.assign({ "Content-Type": "application/json" }, (opts || {}).headers) }
      ));
      if (!res.ok) {
        var err = await res.json().catch(function () { return {}; });
        throw new Error((err.error && err.error.message) || res.statusText);
      }
      return res.status === 204 ? null : res.json();
    },

    // ── Banner ──────────────────────────────────────────────────────────────

    _showBanner: function (msg, type) {
      clearTimeout(this._bannerTimer);
      this.getView().getModel("banner").setData({ msg: msg, type: type || "Information", visible: true });
      if (type === "Success") {
        this._bannerTimer = setTimeout(function () {
          this.getView().getModel("banner").setData({ msg: "", type: "Information", visible: false });
        }.bind(this), 3000);
      }
    },

    onBannerClose: function () {
      this.getView().getModel("banner").setData({ msg: "", type: "Information", visible: false });
    },

    // ── Data loading ────────────────────────────────────────────────────────

    loadList: async function () {
      try {
        var d = await this._fetch("/ReturnOrders?$orderby=createdAt desc&$select=ID,externalOrderRef,customerRef,customerName,companyCode,distributionCenter,receivedDate,status_code,signalStatus,returnAmount,proposedClearing");
        this.getView().getModel("list").setProperty("/orders", d.value);
        this._populateFilterOptions(d.value);
        this._applyFilters();
      } catch (e) {
        this._showBanner(e.message, "Error");
      }
    },

    loadDetail: async function (id) {
      try {
        var results = await Promise.all([
          this._fetch("/ReturnOrders(" + id + ")"),
          this._fetch("/ReturnOrders(" + id + ")/expectedItems"),
          this._fetch("/ReturnOrders(" + id + ")/receivedItems"),
          this._fetch("/ReturnOrders(" + id + ")/auditHistory?$orderby=createdAt desc")
        ]);
        this.getView().getModel("detail").setData({
          order:    results[0],
          expected: results[1].value,
          received: results[2].value,
          history:  results[3].value
        });
      } catch (e) {
        this._showBanner(e.message, "Error");
      }
    },

    // ── Filters ─────────────────────────────────────────────────────────────

    _populateFilterOptions: function (orders) {
      var codeSet = {}, dcSet = {}, custSet = {};
      var codes = [], dcs = [], custs = [];
      orders.forEach(function (o) {
        if (o.companyCode && !codeSet[o.companyCode]) {
          codeSet[o.companyCode] = true;
          codes.push({ key: o.companyCode, text: o.companyCode });
        }
        if (o.distributionCenter && !dcSet[o.distributionCenter]) {
          dcSet[o.distributionCenter] = true;
          dcs.push({ key: o.distributionCenter, text: o.distributionCenter });
        }
        if (o.customerName && !custSet[o.customerName]) {
          custSet[o.customerName] = true;
          custs.push({ key: o.customerName, text: o.customerName });
        }
      });
      codes.sort(function (a, b) { return a.key.localeCompare(b.key); });
      dcs.sort(function (a, b) { return a.key.localeCompare(b.key); });
      custs.sort(function (a, b) { return a.key.localeCompare(b.key); });
      this.getView().getModel("filterOptions").setData({
        companyCodes: codes, distributionCenters: dcs, customerNames: custs
      });
    },

    _applyFilters: function () {
      var aCodes = this.byId("filterCompanyCode").getSelectedKeys();
      var aDCs   = this.byId("filterDC").getSelectedKeys();
      var sDate  = this.byId("filterDate").getValue();
      var aCusts = this.byId("filterCustomerName").getSelectedKeys();

      var orders   = this.getView().getModel("list").getProperty("/orders") || [];
      var filtered = orders.filter(function (o) {
        if (aCodes.length && aCodes.indexOf(o.companyCode)        === -1) return false;
        if (aDCs.length   && aDCs.indexOf(o.distributionCenter)   === -1) return false;
        if (sDate         && o.receivedDate !== sDate)                    return false;
        if (aCusts.length && aCusts.indexOf(o.customerName)       === -1) return false;
        return true;
      });

      if (aCodes.length || aDCs.length || sDate || aCusts.length) {
        console.log("[Filter] " + filtered.length + " of " + orders.length + " orders");
      }

      var matchedArr   = filtered.filter(function (o) { return o.status_code === "MATCHED"; });
      var partialArr   = filtered.filter(function (o) { return o.status_code === "PARTIAL"; });
      var unmatchedArr = filtered.filter(function (o) { return o.status_code === "UNMATCHED"; });

      var oList = this.getView().getModel("list");
      oList.setProperty("/matched",         matchedArr);
      oList.setProperty("/partial",         partialArr);
      oList.setProperty("/unmatched",       unmatchedArr);
      oList.setProperty("/matchedAmount",   matchedArr.reduce(function (s, o) { return s + +(o.returnAmount || 0); }, 0));
      oList.setProperty("/partialAmount",   partialArr.reduce(function (s, o) { return s + +(o.returnAmount || 0); }, 0));
      oList.setProperty("/unmatchedAmount", unmatchedArr.reduce(function (s, o) { return s + +(o.returnAmount || 0); }, 0));
    },

    onFilterChange: function () {
      this._applyFilters();
    },

    onClearFilters: function () {
      this.byId("filterCompanyCode").setSelectedKeys([]);
      this.byId("filterDC").setSelectedKeys([]);
      this.byId("filterDate").setValue("");
      this.byId("filterCustomerName").setSelectedKeys([]);
      this._applyFilters();
    },

    _callAction: async function (action, body) {
      var id = this.getView().getModel("detail").getProperty("/order/ID");
      try {
        await this._fetch("/ReturnOrders(" + id + ")/ExceptionService." + action, {
          method: "POST",
          body: JSON.stringify(body || {})
        });
        this._showBanner(action + " completed successfully", "Success");
        await this.loadDetail(id);
        await this.loadList();
      } catch (e) {
        this._showBanner(e.message, "Error");
      }
    },

    // ── List page handlers ──────────────────────────────────────────────────

    onOrderSelected: async function (evt) {
      var ctx = evt.getParameter("listItem").getBindingContext("list");
      var id  = ctx.getProperty("ID");
      await this.loadDetail(id);
      this.byId("navApp").to(this.byId("detailPage").getId());
    },

    onRefresh: async function () {
      var oPage = this.byId("listPage");
      oPage.setBusy(true);
      console.log("[Refresh] manual refresh triggered");
      try {
        await this.loadList();
        console.log("[Refresh] data reloaded");
      } finally {
        oPage.setBusy(false);
      }
    },

    // ── Auto-refresh polling ────────────────────────────────────────────────

    onExit: function () {
      this._stopPolling();
      clearTimeout(this._bannerTimer);
    },

    _startPolling: function () {
      this._pollTimer = setInterval(this._pollTick.bind(this), POLL_INTERVAL_MS);
    },

    _stopPolling: function () {
      if (this._pollTimer) {
        clearInterval(this._pollTimer);
        this._pollTimer = null;
      }
    },

    _pollTick: async function () {
      // Skip while the tab is hidden — no point waking the backend for an unseen UI.
      if (document.visibilityState === "hidden") return;
      try {
        var marker = await this._fetchChangeMarker();
        if (this._lastChangeMarker === null) {
          // First completed poll — capture the current marker as our baseline.
          // Don't trigger a refresh here; loadList() already ran in onInit.
          this._lastChangeMarker = marker;
          return;
        }
        if (marker !== this._lastChangeMarker) {
          console.log("[AutoRefresh] change detected, refreshing list [marker=" + marker + "]");
          this._lastChangeMarker = marker;
          await this.loadList();
        }
      } catch (e) {
        // Silently suppress poll errors — don't interrupt the user with banners.
        console.warn("[AutoRefresh] poll error:", e.message);
      }
    },

    _fetchChangeMarker: async function () {
      var url = this._svcBase() + "/ChangeState('ReturnOrders')";
      var res = await fetch(url, { headers: { Accept: "application/json" } });
      if (res.status === 404) return null; // no writes have occurred yet
      if (!res.ok) throw new Error("HTTP " + res.status);
      var data = await res.json();
      return data.lastChanged || null;
    },

    onRegenerateProposal: function () {
      this._showBanner("Regenerate Proposal is not yet implemented", "Information");
    },
    onPostConfirmedItems: function () {
      this._showBanner("Post Confirmed Items is not yet implemented", "Information");
    },
    onResetRun: function () {
      this._showBanner("Reset Run is not yet implemented", "Information");
    },

    // ── Detail page handlers ────────────────────────────────────────────────

    onNavBack: function () {
      this.byId("navApp").back();
      this.getView().getModel("banner").setData({ msg: "", type: "Information", visible: false });
    },

    onConfirm:     function () { this._callAction("confirm"); },
    onRetrySignal: function () { this._callAction("retrySignal"); },

    onOpenEscalate: function () {
      this.byId("escalateReason").setValue("");
      this.byId("escalateDialog").open();
    },
    onEscalateConfirm: function () {
      var reason = this.byId("escalateReason").getValue();
      this.byId("escalateDialog").close();
      this._callAction("escalate", { reason: reason });
    },
    onEscalateCancel: function () { this.byId("escalateDialog").close(); },

    onOpenResolve: function () {
      this.byId("resolveReason").setValue("");
      this.byId("resolveDialog").open();
    },
    onResolveConfirm: function () {
      var decision = this.byId("resolveDecision").getSelectedKey();
      var reason   = this.byId("resolveReason").getValue();
      this.byId("resolveDialog").close();
      this._callAction("resolve", { decision: decision, reason: reason });
    },
    onResolveCancel: function () { this.byId("resolveDialog").close(); },

    onOpenReject: function () {
      this.byId("rejectReason").setValue("");
      this.byId("rejectDialog").open();
    },
    onRejectConfirm: function () {
      var reason = this.byId("rejectReason").getValue();
      this.byId("rejectDialog").close();
      this._callAction("reject", { reason: reason });
    },
    onRejectCancel: function () { this.byId("rejectDialog").close(); },

    onOpenLink: function () {
      this.byId("linkOrderId").setValue("");
      this.byId("linkReason").setValue("");
      this.byId("linkDialog").open();
    },
    onLinkConfirm: function () {
      var linkedOrderId = this.byId("linkOrderId").getValue();
      var reason        = this.byId("linkReason").getValue();
      this.byId("linkDialog").close();
      this._callAction("linkOrder", { linkedOrderId: linkedOrderId, reason: reason });
    },
    onLinkCancel: function () { this.byId("linkDialog").close(); },

    // ── Formatters ──────────────────────────────────────────────────────────

    formatStatusText: function (code) {
      var map = {
        MATCHED:            "Matched",
        PARTIAL:            "Partial",
        UNMATCHED:          "Unmatched",
        RESOLVED_CONFIRMED: "Confirmed",
        RESOLVED_REJECTED:  "Rejected",
        RESOLVED_LINKED:    "Linked",
        PENDING_SIGNAL:     "Pending Signal"
      };
      return map[code] || code || "—";
    },

    formatStatusState: function (code) {
      var map = {
        MATCHED:            "Warning",
        PARTIAL:            "Warning",
        UNMATCHED:          "Error",
        RESOLVED_CONFIRMED: "Success",
        RESOLVED_REJECTED:  "None",
        RESOLVED_LINKED:    "Success",
        PENDING_SIGNAL:     "None"
      };
      return map[code] || "None";
    },

    formatSignalText:  function (code) { return code || "—"; },
    formatSignalState: function (code) {
      return code === "SENT" ? "Success" : code === "FAILED" ? "Error" : "None";
    },

    formatTimestamp: function (v) { return v ? new Date(v).toLocaleString() : "—"; },
    formatValue:     function (v) { return v || "—"; },
    formatAmount:    function (v) { return "$" + (+(v || 0)).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  });
});
