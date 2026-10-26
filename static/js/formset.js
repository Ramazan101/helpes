document.addEventListener("DOMContentLoaded", function () {
    const addBtn = document.getElementById("addEquipmentRowBtn");
    const container = document.getElementById("equipmentRowsContainer");
    const totalFormsInput = document.getElementById("id_items-TOTAL_FORMS");
    if (!addBtn || !container || !totalFormsInput) return;

    function reindexRows() {
        const rows = container.querySelectorAll(".equipment-row");
        totalFormsInput.value = rows.length;
        rows.forEach(function (row, idx) {
            row.querySelectorAll("select, input, label").forEach(function (el) {
                if (el.name) {
                    el.name = el.name.replace(/items-\d+-/, "items-" + idx + "-");
                }
                if (el.id) {
                    el.id = el.id.replace(/id_items-\d+-/, "id_items-" + idx + "-");
                }
            });
            const removeBtn = row.querySelector(".remove-equipment-row-btn");
            if (removeBtn) {
                removeBtn.disabled = rows.length <= 1;
            }
        });
    }

    addBtn.addEventListener("click", function () {
        const firstRow = container.querySelector(".equipment-row");
        if (!firstRow) return;

        const newRow = firstRow.cloneNode(true);
        const select = newRow.querySelector("select");
        const qty = newRow.querySelector("input[type='number']");
        if (select) select.value = "";
        if (qty) qty.value = "1";
        newRow.querySelectorAll(".text-danger").forEach(function (err) {
            err.remove();
        });

        container.appendChild(newRow);
        reindexRows();
    });

    container.addEventListener("click", function (event) {
        const btn = event.target.closest(".remove-equipment-row-btn");
        if (!btn) return;
        const rows = container.querySelectorAll(".equipment-row");
        if (rows.length <= 1) return;
        const row = btn.closest(".equipment-row");
        if (row) {
            row.remove();
            reindexRows();
        }
    });

    reindexRows();
});
