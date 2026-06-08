// Vanilla-JS pagination for long tables. Auto-applies to any
// `article table:not([class])` with more than PAGE_SIZE rows; the
// Proposals index page is currently the only table that meets that
// bar. Other tables (capability table, etc.) are short enough to
// fall through without pagination.
//
// Composes with the existing tablesort.js: tablesort reorders rows
// in place; this script re-runs `showPage(currentPage)` on the
// Tablesort 5.x `afterSort` event so the sorted order is paginated
// consistently.
//
// URL hash sync: `#page-N` persists the current page across reloads
// and shared links. With JS disabled, the full table renders
// normally (graceful degrade — every row visible, no controls).
document$.subscribe(function () {
  var PAGE_SIZE = 20;
  var tables = document.querySelectorAll("article table:not([class])");
  tables.forEach(function (table) {
    var tbody = table.querySelector("tbody");
    if (!tbody) return;
    if (tbody.rows.length <= PAGE_SIZE) return;
    setupPagination(table, tbody, PAGE_SIZE);
  });

  function setupPagination(table, tbody, pageSize) {
    // Idempotency guard — if `document$.subscribe` fires twice on
    // the same page (defensive against Material's Instant Loading
    // edge cases), skip the second wiring rather than appending a
    // second nav element.
    if (table.dataset.paginated) return;
    table.dataset.paginated = "true";

    var currentPage = parsePageFromHash() || 1;
    var nav = renderNav(table);

    function showPage(n) {
      var allRows = Array.from(tbody.rows);
      var totalPages = Math.ceil(allRows.length / pageSize);
      if (n < 1) n = 1;
      if (n > totalPages) n = totalPages;
      currentPage = n;

      allRows.forEach(function (row, i) {
        var page = Math.floor(i / pageSize) + 1;
        row.style.display = page === n ? "" : "none";
      });

      updateNav(nav, n, totalPages);
      window.history.replaceState(null, "", "#page-" + n);
    }

    nav.addEventListener("click", function (e) {
      if (e.target.tagName !== "BUTTON") return;
      e.preventDefault();
      var action = e.target.dataset.action;
      if (action === "prev") showPage(currentPage - 1);
      else if (action === "next") showPage(currentPage + 1);
    });

    // Re-paginate after the user activates a sortable column header
    // (Tablesort 5.x emits an `afterSort` event on the table element
    // once row reorder completes; fires on both mouse + keyboard
    // activation).
    table.addEventListener("afterSort", function () { showPage(currentPage); });

    showPage(currentPage);
  }

  function renderNav(table) {
    var nav = document.createElement("nav");
    nav.className = "table-pagination";
    nav.setAttribute("aria-label", "Table pagination");
    table.parentNode.insertBefore(nav, table.nextSibling);
    return nav;
  }

  function updateNav(nav, currentPage, totalPages) {
    nav.innerHTML = "";
    var btn = function (action, label, disabled) {
      var b = document.createElement("button");
      b.type = "button";
      b.dataset.action = action;
      b.textContent = label;
      if (disabled) b.disabled = true;
      return b;
    };
    nav.appendChild(btn("prev", "← Prev", currentPage === 1));
    var info = document.createElement("span");
    info.className = "table-pagination__info";
    // `aria-live="polite"` so screen readers announce page changes
    // when the user navigates via Prev / Next.
    info.setAttribute("aria-live", "polite");
    info.textContent = "Page " + currentPage + " of " + totalPages;
    nav.appendChild(info);
    nav.appendChild(btn("next", "Next →", currentPage === totalPages));
  }

  function parsePageFromHash() {
    var match = window.location.hash.match(/page-(\d+)/);
    return match ? parseInt(match[1], 10) : null;
  }
});
