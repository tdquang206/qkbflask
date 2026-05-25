/**
 * static/exams_list.js
 * 
 * Interactive client-side logic for the Exam List (Danh sách toa thuốc) page.
 * Optimized for local/desktop offline use:
 * - Real-time client-side stats calculation based on multi-month selection.
 * - Fast client-side sorting of the global unpaid list.
 * - Dynamic reactive toggle for months (removes server roundtrips).
 * - Multi-view synchronization when marking an exam as paid.
 * 
 * No external icon libraries or CDNs are used.
 */

document.addEventListener("DOMContentLoaded", () => {
    // ----------------------------------------------------
    // State & Constants
    // ----------------------------------------------------
    const defaultMonths = JSON.parse(document.getElementById("default-selected-months-data").textContent || "[]");
    let activeMonths = [...defaultMonths];
    let unpaidSortAscending = false; // default is newest first (descending)

    // Elements
    const monthButtons = document.querySelectorAll(".month-tab-btn");
    const monthSections = document.querySelectorAll(".month-section");
    const unpaidTableBody = document.getElementById("unpaid-tbody");
    const unpaidSortBtn = document.getElementById("unpaid-sort-btn");

    // Stats Elements
    const statTotalRecords = document.getElementById("stat-total-records");
    const statSubtotalPaid = document.getElementById("stat-subtotal-paid");
    const statSubtotalUnpaid = document.getElementById("stat-subtotal-unpaid");
    const statTotalExpected = document.getElementById("stat-total-expected");

    // ----------------------------------------------------
    // Helper Functions
    // ----------------------------------------------------
    
    /**
     * Format numbers into Vietnamese currency format (e.g. 150,000đ)
     */
    function formatCurrency(amount) {
        return amount.toLocaleString("vi-VN") + "đ";
    }

    /**
     * Parse currency or number from a raw data attribute
     */
    function parseValue(val) {
        const parsed = parseInt(val, 10);
        return isNaN(parsed) ? 0 : parsed;
    }

    /**
     * Update the active CSS classes on the month buttons based on activeMonths array
     */
    function updateMonthButtonUI() {
        monthButtons.forEach(btn => {
            const month = btn.getAttribute("data-month");
            if (activeMonths.includes(month)) {
                btn.classList.remove("is-light", "is-outlined");
                btn.classList.add("is-primary");
            } else {
                btn.classList.remove("is-primary");
                btn.classList.add("is-light", "is-outlined");
            }
        });
    }

    /**
     * Dynamic calculations: computes records count, paid/unpaid totals
     * for all active months, and updates stats display panels.
     */
    function recalculateStats() {
        let totalCount = 0;
        let totalPaid = 0;
        let totalUnpaid = 0;

        monthSections.forEach(section => {
            const month = section.getAttribute("data-month");
            if (activeMonths.includes(month)) {
                // Read pre-computed values from data attributes on the HTML container
                const count = parseValue(section.getAttribute("data-total-records"));
                const paid = parseValue(section.getAttribute("data-subtotal-paid"));
                const unpaid = parseValue(section.getAttribute("data-subtotal-unpaid"));

                totalCount += count;
                totalPaid += paid;
                totalUnpaid += unpaid;
            }
        });

        // Update UI with calculated values
        statTotalRecords.textContent = totalCount;
        statSubtotalPaid.textContent = formatCurrency(totalPaid);
        statSubtotalUnpaid.textContent = formatCurrency(totalUnpaid);
        statTotalExpected.textContent = formatCurrency(totalPaid + totalUnpaid);
    }

    /**
     * Updates visibility of month sections based on activeMonths array.
     */
    function filterMonthSections() {
        monthSections.forEach(section => {
            const month = section.getAttribute("data-month");
            if (activeMonths.includes(month)) {
                section.style.display = "block";
            } else {
                section.style.display = "none";
            }
        });
    }

    /**
     * Toggles month selection and applies fallback behavior.
     */
    function toggleMonth(month) {
        const index = activeMonths.indexOf(month);
        if (index > -1) {
            // Deselect month
            activeMonths.splice(index, 1);
        } else {
            // Select month
            activeMonths.push(month);
        }

        // Deselection fallback: if empty, revert back to default last 3 months
        if (activeMonths.length === 0) {
            activeMonths = [...defaultMonths];
        }

        updateMonthButtonUI();
        filterMonthSections();
        recalculateStats();
    }

    // ----------------------------------------------------
    // Sorting: Global Unpaid Table
    // ----------------------------------------------------
    if (unpaidSortBtn && unpaidTableBody) {
        unpaidSortBtn.addEventListener("click", () => {
            unpaidSortAscending = !unpaidSortAscending;

            // Toggle UI button text cleanly without icons
            if (unpaidSortAscending) {
                unpaidSortBtn.textContent = "Sắp xếp: Cũ nhất ➔ Mới nhất";
            } else {
                unpaidSortBtn.textContent = "Sắp xếp: Mới nhất ➔ Cũ nhất";
            }

            // Get row elements, sort them based on the data-date attribute
            const rows = Array.from(unpaidTableBody.querySelectorAll("tr"));
            rows.sort((rowA, rowB) => {
                const dateA = rowA.getAttribute("data-date") || "";
                const dateB = rowB.getAttribute("data-date") || "";

                if (unpaidSortAscending) {
                    return dateA.localeCompare(dateB); // Ascending (Oldest first)
                } else {
                    return dateB.localeCompare(dateA); // Descending (Newest first)
                }
            });

            // Re-append sorted rows and adjust the display indices (#)
            rows.forEach((row, idx) => {
                const indexCell = row.cells[0];
                if (indexCell) {
                    indexCell.textContent = idx + 1;
                }
                unpaidTableBody.appendChild(row);
            });
        });
    }

    // ----------------------------------------------------
    // Event Listeners for Month Selector
    // ----------------------------------------------------
    monthButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const month = btn.getAttribute("data-month");
            toggleMonth(month);
        });
    });

    // ----------------------------------------------------
    // Payment Toggle & Synced Updates
    // ----------------------------------------------------
    function setupPaymentButtons() {
        document.querySelectorAll(".money_received_btn").forEach(btn => {
            // Avoid duplicate registrations
            if (btn.dataset.registered) return;
            btn.dataset.registered = "true";

            btn.addEventListener("click", async function () {
                try {
                    const examId = btn.getAttribute("data-exam-id");
                    const patientId = btn.getAttribute("data-patient-id");
                    
                    // Find the row containing this button
                    const row = btn.closest("tr");
                    let realAmount = null;
                    if (row) {
                        const input = row.querySelector(".real_amount_input");
                        if (input) {
                            realAmount = input.value;
                        }
                    }

                    const payload = { patient_id: patientId, exam_id: examId };
                    if (realAmount !== null) {
                        payload.real_amount = realAmount;
                    }

                    const response = await fetch("/api/mark_paid", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });

                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.error || `HTTP error! status: ${response.status}`);
                    }

                    if (data.success) {
                        // Success! Update all occurrences of this exam across all views (top panel & monthly sections)
                        document.querySelectorAll(`[data-exam-id="${examId}"]`).forEach(actionBtn => {
                            const btnRow = actionBtn.closest("tr");
                            if (btnRow) {
                                // Disable real_amount input
                                const input = btnRow.querySelector(".real_amount_input");
                                if (input) {
                                    input.disabled = true;
                                }
                            }
                            
                            // Transform button into static success tag
                            if (actionBtn.tagName === "A" || actionBtn.tagName === "BUTTON") {
                                const parent = actionBtn.parentElement;
                                if (parent) {
                                    // Replace button cleanly
                                    actionBtn.remove();
                                    const successSpan = document.createElement("span");
                                    successSpan.className = "tag is-success";
                                    successSpan.textContent = "Đã nhận tiền";
                                    parent.appendChild(successSpan);
                                }
                            }
                        });

                        showToast("✅ Đã lưu thành công!", "is-success");
                    } else {
                        throw new Error(data.error || "Unknown error occurred.");
                    }
                } catch (error) {
                    console.error("Mark paid error:", error);
                    showToast(`Lỗi: ${error.message}`, "is-danger");
                }
            });
        });
    }

    // Initialize UI elements on load
    updateMonthButtonUI();
    filterMonthSections();
    recalculateStats();
    setupPaymentButtons();
});
