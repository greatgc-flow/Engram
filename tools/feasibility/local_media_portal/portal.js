"use strict";

for (const panel of document.querySelectorAll("[data-filter-section]")) {
  const rows = Array.from(panel.querySelectorAll(".row"), (element) => ({
    element,
    text: element.textContent.normalize("NFC").toLowerCase(),
  }));
  if (!rows.length) continue;

  const filters = panel.querySelector(".filters");
  const query = panel.querySelector("[data-query]");
  const selects = Array.from(panel.querySelectorAll("[data-field]"));
  const count = panel.querySelector("[data-count]");
  const empty = panel.querySelector("[data-empty]");
  count.hidden = false;
  filters.hidden = false;
  empty.textContent = "No results match these filters.";

  function update() {
    const term = query.value.trim().normalize("NFC").toLowerCase();
    let visible = 0;
    for (const { element, text } of rows) {
      const matches = selects.every((select) => !select.value || element.dataset[select.dataset.field] === select.value);
      element.hidden = !matches || !text.includes(term);
      if (!element.hidden) visible += 1;
    }
    count.textContent = `${visible} of ${rows.length} shown`;
    empty.hidden = visible > 0;
  }

  query.addEventListener("input", update);
  for (const select of selects) select.addEventListener("change", update);
  update();
}
