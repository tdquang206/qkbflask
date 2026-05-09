/* new_exam.js — exam form behaviour for new_exam.html */

// Back button
document.getElementById("backBtn").addEventListener("click", function () {
  window.location.href = "/patients"
});

// Calculate drug + service totals
function calculateTotals() {
  // drugs
  const tableBody = document.getElementById("drugTableBody");
  const rows = tableBody.querySelectorAll("tr");
  let qtySum = 0, priceSum = 0;
  rows.forEach(row => {
    const qty = parseInt(row.querySelector(".quantity").textContent) || 0;
    const price = parseFloat(row.dataset.price) || 0;
    qtySum += qty;
    priceSum += qty * price;
  });

  // services
  let serviceSum = 0;
  const serviceRows = document.querySelectorAll("#serviceTableBody tr");
  serviceRows.forEach(row => {
    const price = parseFloat(row.dataset.price) || 0;
    serviceSum += price;
  });

  let total = priceSum + serviceSum;

  // override
  const overrideVal = parseFloat(document.getElementById('total_override')?.value || 0);
  if (!isNaN(overrideVal) && overrideVal > 0) {
    total = overrideVal;
  }

  document.getElementById("totalQuantity").textContent = qtySum;
  document.getElementById("totalPrice").textContent = total.toLocaleString();
  document.querySelector("input[name='total_money']").value = total;
}

// Progress modal / form submit
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("examForm");
  const saveBtn = document.getElementById("saveBtn");
  const modal = document.getElementById("progressModal");
  const errorMsg = document.getElementById("errorMsg");
  const printBtn = document.getElementById("printBtn");
  let shouldPrintAfterSave = false;
  let currentPdfUrl = null;

  if (printBtn) {
    printBtn.addEventListener("click", (e) => {
      e.preventDefault();
      shouldPrintAfterSave = true;
      // Trigger form submit
      form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    });
  }

  // Helper to update status
  function updateStatus(elementId, status) {
    const el = document.getElementById(elementId);
    const iconSpan = el.querySelector(".icon");
    if (status === 'working') {
      iconSpan.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
      el.style.color = 'black';
    } else if (status === 'success') {
      iconSpan.innerHTML = '✅';
      el.style.color = 'green';
    } else if (status === 'error') {
      iconSpan.innerHTML = '❌';
      el.style.color = 'red';
    }
  }

  // Helper to call API
  async function callStep(url, data) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    let body = {};
    try {
      body = await res.json();
    } catch (_) {
      body = {};
    }
    return {
      ok: res.ok,
      statusCode: res.status,
      body
    };
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    // 1. Show Modal & Reset
    modal.classList.add("is-active");
    errorMsg.classList.add("is-hidden");
    updateStatus("stepSave", "working");
    updateStatus("stepPdf", "working");
    updateStatus("stepDiscord", "working");

    try {
      // STEP 1: Save Data
      // Replace any file-input lab_image entries with our DataTransfer-managed pending files
      const formData = new FormData(this);
      formData.delete('lab_image');
      for (const f of pendingDT.files) formData.append('lab_image', f);

      const res1 = await fetch(this.action, {
        method: "POST",
        body: formData
      });
      const data1 = await res1.json();

      if (data1.status !== "success") {
        throw new Error(data1.message || "Lỗi lưu dữ liệu");
      }
      updateStatus("stepSave", "success");

      const payload = {
        exam_id: data1.exam_id,
        patient_id: data1.patient_id
      };

      // STEP 2: Generate Files
      updateStatus("stepPdf", "working");
      try {
        const res2 = await callStep('/api/exam/generate_files', payload);
        const step2Ok = res2.ok && (res2.body.status === 'success' || res2.body.success === true);
        if (step2Ok) {
          updateStatus("stepPdf", "success");
          if (res2.body.pdf_url) {
            currentPdfUrl = res2.body.pdf_url;
          }
        } else {
          console.error(res2);
          if (res2.body && res2.body.message) {
            errorMsg.textContent = res2.body.message;
            errorMsg.classList.remove("is-hidden");
          }
          updateStatus("stepPdf", "error");
        }
      } catch (errPdf) {
        console.error(errPdf);
        errorMsg.textContent = errPdf.message || 'Lỗi không xác định khi tạo PDF/JPEG';
        errorMsg.classList.remove("is-hidden");
        updateStatus("stepPdf", "error");
      }

      // STEP 3: Discord
      const discordCheckbox = document.querySelector("input[name='send_discord']");
      if (discordCheckbox && discordCheckbox.checked) {
        updateStatus("stepDiscord", "working");
        try {
          const res3 = await callStep('/api/exam/send_discord', payload);
          const step3Ok = res3.ok && (res3.body.status === 'success' || res3.body.success === true);
          if (step3Ok) {
            updateStatus("stepDiscord", "success");
          } else {
            console.error(res3);
            updateStatus("stepDiscord", "error");
          }
        } catch (errDis) {
          console.error(errDis);
          updateStatus("stepDiscord", "error");
        }
      } else {
        document.getElementById("stepDiscord").innerHTML = '<span class="icon">⏭️</span> <span>Gửi Discord (Bỏ qua)</span>';
      }

      // DONE: Close Modal & Handle Printing/Redirect
      setTimeout(() => {
        modal.classList.remove("is-active");
        showToast("✅ Đã lưu xong!", "is-success");

        if (shouldPrintAfterSave && currentPdfUrl) {
          window.open(currentPdfUrl, "_blank");
        }
        shouldPrintAfterSave = false;

        // If it was a new exam, we redirect to the edit page
        if (data1.redirect_url) {
          window.location.href = data1.redirect_url;
        }
      }, 500);

    } catch (err) {
      console.error(err);
      updateStatus("stepSave", "error");
      errorMsg.textContent = err.message;
      errorMsg.classList.remove("is-hidden");
      modal.classList.remove("is-active");
    }
  });
});

// Flatpickr: exam date
document.addEventListener("DOMContentLoaded", function () {
  flatpickr("input[name='exam_date']", {
    dateFormat: "Y-m-d",
    defaultDate: document.querySelector("input[name='exam_date']").value || "today"
  });

  flatpickr("input[name='expected_date']", {
    dateFormat: "Y-m-d",
    defaultDate: document.querySelector("input[name='expected_date']").value || null,
    minDate: "today"
  });
});

// Re-exam date calculation
document.addEventListener("DOMContentLoaded", () => {
  const examInput = document.getElementById("exam_date") || document.querySelector("input[name='exam_date']");
  const daysInput = document.getElementById("re_exam_after_days");
  const expectedInput = document.getElementById("expected_date");

  function parseDateLike(value) {
    if (!value) return null;
    const d = new Date(value);
    return isNaN(d) ? null : d;
  }

  function addDaysTo(dateLike, days) {
    const base = parseDateLike(dateLike);
    if (!base) return null;
    const d = new Date(base);
    d.setDate(d.getDate() + Number(days));
    return d;
  }

  const reexamPicker = flatpickr(expectedInput, {
    dateFormat: "Y-m-d",
    altInput: true,
    altFormat: "l d/m/Y",
    allowInput: true,
    locale: {
      firstDayOfWeek: 1,
      weekdays: { shorthand: ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'], longhand: ['Chủ Nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'] },
      months: { shorthand: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'], longhand: ['Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4', 'Tháng 5', 'Tháng 6', 'Tháng 7', 'Tháng 8', 'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12'] }
    },
    onChange(selectedDates) {
      if (!selectedDates.length || !examInput || !examInput.value) return;
      const examDate = parseDateLike(examInput.value);
      if (!examDate) return;
      const diff = Math.round((selectedDates[0] - examDate) / (1000 * 60 * 60 * 24));
      daysInput.value = diff;
      if (diff <= 0) {
        reexamPicker.clear();
        expectedInput.value = "";
        if (expectedInput._flatpickr && expectedInput._flatpickr.altInput) expectedInput._flatpickr.altInput.value = "";
      }
    }
  });

  function clearExpected() {
    reexamPicker.clear();
    if (expectedInput._flatpickr && expectedInput._flatpickr.altInput) expectedInput._flatpickr.altInput.value = "";
    expectedInput.value = "";
  }

  function updateExpectedFromDays() {
    const daysRaw = daysInput.value;
    const days = daysRaw === "" ? null : Number(daysRaw);
    const examVal = examInput ? examInput.value : null;
    if (!examVal) { clearExpected(); return; }
    if (days === null || isNaN(days) || days <= 0) { clearExpected(); return; }
    const newDate = addDaysTo(examVal, days);
    if (!newDate) { clearExpected(); return; }
    reexamPicker.setDate(newDate, true);
  }

  daysInput.addEventListener("input", updateExpectedFromDays);
  daysInput.addEventListener("change", updateExpectedFromDays);

  if (examInput) {
    examInput.addEventListener("input", updateExpectedFromDays);
    examInput.addEventListener("change", updateExpectedFromDays);
  }

  (function init() {
    if (examInput && !examInput.value) {
      examInput.value = new Date().toISOString().slice(0, 10);
    }
    updateExpectedFromDays();
  })();
});

// Drug list, drug table management
document.addEventListener("DOMContentLoaded", async function () {
  const drugSelect = document.getElementById("drugSelect");
  const drugQty = document.getElementById("drugQty");
  const addDrugBtn = document.getElementById("addDrugBtn");
  const tableBody = document.querySelector("#drugTable tbody");

  let currentSelectedDrug = null;

  let drugList = [];
  try {
    const res = await fetch("/api/drugs");
    drugList = await res.json();
    drugList.sort((a, b) => a.name.localeCompare(b.name));

  } catch (err) {
    console.error("Failed to load drugs", err);
  }

  const input = document.getElementById("drugInput");
  const dropdown = document.getElementById("drugDropdown");
  let activeIndex = -1;


  input.addEventListener("input", () => {
    const value = input.value.toLowerCase();
    dropdown.innerHTML = "";
    if (!value) {
      dropdown.style.display = "none";
      return;
    }

    const matches = drugList.filter(d => d.name.toLowerCase().includes(value));
    if (matches.length) {
      matches.forEach(drug => {
        const option = document.createElement("div");
        option.className = "dropdown-item drug-item";
        option.textContent = drug.name.concat("- M ", drug.buy_price);

        option.style.backgroundColor = "white";
        option.style.color = "black";
        option.onclick = () => {
          input.value = drug.name;
          dropdown.style.display = "none";

          // Optional: store price or other data
          input.dataset.price = drug.sell_price;
        };
        dropdown.appendChild(option);
      });
      dropdown.style.display = "block";
    } else {
      dropdown.style.display = "none";
    }
  });

  // Keyboard navigation
  input.addEventListener("keydown", (e) => {
    const items = dropdown.querySelectorAll(".dropdown-item");
    if (!items.length || dropdown.style.display === "none") return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % items.length;
      updateActive(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + items.length) % items.length;
      updateActive(items);
    } else if (e.key === "Enter" || e.key === "Tab") {
      if (activeIndex >= 0 && activeIndex < items.length) {
        e.preventDefault();
        const selectedName = items[activeIndex].textContent.trim();
        input.value = selectedName;

        // FIX: Update the selected drug object for consistency
        const selectedDrug = drugList.find(d => d.name === selectedName);
        currentSelectedDrug = selectedDrug;

        dropdown.style.display = "none";
        drugQty.focus();
      }
    }
  });

  function updateActive(items) {
    items.forEach((item, i) => {
      item.classList.toggle("has-background-primary", i === activeIndex);
      item.classList.toggle("has-text-white", i === activeIndex);
    });
  }

  function updateRowNumbers() {
    tableBody.querySelectorAll("tr").forEach((row, idx) => {
      row.querySelector("td").textContent = idx + 1;
    });
  }

  function recalcTotals() {
    const rows = document.querySelectorAll("#drugTableBody tr");
    let totalQty = 0;
    let totalPrice = 0;

    rows.forEach((row, idx) => {
      // update row number
      row.querySelector("td").textContent = idx + 1;

      const qty = parseInt(row.querySelector(".quantity").textContent) || 0;
      const price = parseFloat(row.dataset.price) || 0;

      totalQty += qty;
      totalPrice += qty * price;
    });

    document.getElementById("totalQuantity").textContent = totalQty;
    document.getElementById("totalPrice").textContent = totalPrice.toLocaleString();
    // recalc overall which includes services/override
    calculateTotals();
  }

  function appendHiddenInput(parent, inputName, inputValue) {
    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = inputName;
    hidden.value = String(inputValue ?? "");
    parent.appendChild(hidden);
  }

  // Run once on page load (for prefilled exams)
  recalcTotals();

  // After adding a drug (handled below in the full addDrugBtn handler)

  // After removing a drug
  document.querySelector("#drugTableBody").addEventListener("click", (e) => {
    if (e.target.classList.contains("removeRow")) {
      e.target.closest("tr").remove();
      recalcTotals();
    }
  });


    // ===== Enhanced service management =====
    let serviceList = [];
    try {
      const res = await fetch("/api/services");
      serviceList = await res.json();
      serviceList.sort((a, b) => a.name.localeCompare(b.name));
    } catch (err) {
      console.error("Failed to load services", err);
    }

    const serviceInput = document.getElementById("serviceInput");
    const serviceDropdown = document.getElementById("serviceDropdown");
    const serviceQty = document.getElementById("serviceQty");
    const serviceNote = document.getElementById("serviceNote");
    const addServiceBtn = document.getElementById("addServiceBtn");
    const serviceTableBody = document.getElementById("serviceTableBody");
    let activeServiceIndex = -1;
    let currentSelectedService = null;

    serviceInput.addEventListener("input", () => {
      const value = serviceInput.value.toLowerCase();
      serviceDropdown.innerHTML = "";
      if (!value) {
        serviceDropdown.style.display = "none";
        return;
      }
      // Group by department
      const grouped = {};
      serviceList.forEach(s => {
        if (s.name.toLowerCase().includes(value)) {
          const dept = s.department || "Khác";
          if (!grouped[dept]) grouped[dept] = [];
          grouped[dept].push(s);
        }
      });
      let hasAny = false;
      Object.keys(grouped).forEach(dept => {
        const deptDiv = document.createElement("div");
        deptDiv.textContent = dept;
        deptDiv.style.fontWeight = "bold";
        deptDiv.style.background = "#f5f5f5";
        deptDiv.style.padding = "4px 8px";
        serviceDropdown.appendChild(deptDiv);
        grouped[dept].forEach(s => {
          const option = document.createElement("div");
          option.className = "dropdown-item service-item";
          option.textContent = `${s.name} (${s.department || ''}) - ${s.price.toLocaleString()}đ`;
          option.style.backgroundColor = "white";
          option.style.color = "black";
          option.onclick = () => {
            serviceInput.value = s.name;
            serviceInput.dataset.serviceId = s.id;
            serviceInput.dataset.price = s.price;
            serviceInput.dataset.department = s.department || "";
            currentSelectedService = s;
            serviceDropdown.style.display = "none";
            serviceQty.focus();
          };
          serviceDropdown.appendChild(option);
          hasAny = true;
        });
      });
      serviceDropdown.style.display = hasAny ? "block" : "none";
    });

    serviceInput.addEventListener("keydown", (e) => {
      const items = serviceDropdown.querySelectorAll(".service-item");
      if (!items.length || serviceDropdown.style.display === "none") return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeServiceIndex = (activeServiceIndex + 1) % items.length;
        updateActiveService(items);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeServiceIndex = (activeServiceIndex - 1 + items.length) % items.length;
        updateActiveService(items);
      } else if (e.key === "Enter" || e.key === "Tab") {
        if (activeServiceIndex >= 0 && activeServiceIndex < items.length) {
          e.preventDefault();
          items[activeServiceIndex].click();
        }
      }
    });

    function updateActiveService(items) {
      items.forEach((item, i) => {
        item.classList.toggle("has-background-primary", i === activeServiceIndex);
        item.classList.toggle("has-text-white", i === activeServiceIndex);
      });
    }

    function updateServiceRowNumbers() {
      serviceTableBody.querySelectorAll("tr").forEach((row, idx) => {
        row.querySelector("td").textContent = idx + 1;
      });
    }

    addServiceBtn.addEventListener("click", () => {
      const name = serviceInput.value.trim();
      const qty = parseInt(serviceQty.value) || 1;
      const note = serviceNote.value || "";
      const s = currentSelectedService || serviceList.find(x => x.name === name);
      if (!s) {
        alert("Vui lòng chọn dịch vụ từ danh sách gợi ý.");
        return;
      }
      const price = s.price;
      const subtotal = qty * price;
      const row = document.createElement("tr");
      row.dataset.price = subtotal;
      row.dataset.serviceId = s.id;

      const indexCell = document.createElement("td");
      const nameCell = document.createElement("td");
      const deptCell = document.createElement("td");
      const qtyCell = document.createElement("td");
      const noteCell = document.createElement("td");
      const priceCell = document.createElement("td");
      const subtotalCell = document.createElement("td");
      const actionCell = document.createElement("td");
      const removeBtn = document.createElement("button");

      nameCell.textContent = s.name;
      appendHiddenInput(nameCell, "service_name", s.name);
      appendHiddenInput(nameCell, "service_id", s.id);
      deptCell.textContent = s.department || "";
      appendHiddenInput(deptCell, "service_department", s.department || "");
      qtyCell.textContent = String(qty);
      appendHiddenInput(qtyCell, "service_quantity", qty);
      noteCell.textContent = note;
      appendHiddenInput(noteCell, "service_note", note);
      priceCell.className = "has-text-right";
      priceCell.textContent = price.toLocaleString();
      appendHiddenInput(priceCell, "service_price", price);
      subtotalCell.className = "has-text-right";
      subtotalCell.textContent = subtotal.toLocaleString();
      appendHiddenInput(subtotalCell, "service_subtotal", subtotal);

      removeBtn.type = "button";
      removeBtn.className = "button is-small is-danger removeServiceRow";
      removeBtn.textContent = "X";
      actionCell.appendChild(removeBtn);

      row.appendChild(indexCell);
      row.appendChild(nameCell);
      row.appendChild(deptCell);
      row.appendChild(qtyCell);
      row.appendChild(noteCell);
      row.appendChild(priceCell);
      row.appendChild(subtotalCell);
      row.appendChild(actionCell);
      serviceTableBody.appendChild(row);
      updateServiceRowNumbers();
      calculateTotals();
      // reset inputs
      serviceInput.value = "";
      serviceQty.value = "";
      serviceNote.value = "";
      currentSelectedService = null;
      serviceDropdown.style.display = "none";
    });

    serviceTableBody.addEventListener("click", (e) => {
      if (e.target.classList.contains("removeServiceRow")) {
        e.target.closest("tr").remove();
        updateServiceRowNumbers();
        calculateTotals();
      }
    });

  // on service_fee changes
  document.querySelectorAll("input[name='service_fee']").forEach(radio => {
    radio.addEventListener("change", calculateTotals);
  });

  addDrugBtn.addEventListener("click", () => {
    const input = document.getElementById("drugInput");
    const name = input.value.trim();
    if (!name) return;

    // Find the drug in drugList to get the price
    const drug = drugList.find(d => d.name.trim() === name.trim());
    const price = drug ? drug.sell_price : 0;

    if (!drug) {
      alert("Vui lòng chọn thuốc từ danh sách gợi ý.");
      return;
    }

    const qty = parseInt(document.getElementById("drugQty").value) || 1;
    const note = document.getElementById("drugNote").value || "";

    const row = document.createElement("tr");
    row.dataset.price = price;

    const indexCell = document.createElement("td");
    const nameCell = document.createElement("td");
    const quantityCell = document.createElement("td");
    const noteCell = document.createElement("td");
    const priceCell = document.createElement("td");
    const actionCell = document.createElement("td");
    const removeBtn = document.createElement("button");

    nameCell.textContent = name;
    appendHiddenInput(nameCell, "drug_name", name);

    quantityCell.className = "quantity";
    quantityCell.textContent = String(qty);
    appendHiddenInput(quantityCell, "drug_quantity", qty);

    noteCell.textContent = note;
    appendHiddenInput(noteCell, "drug_note", note);

    priceCell.hidden = true;
    priceCell.textContent = String(price);
    appendHiddenInput(priceCell, "drug_price", price);

    removeBtn.type = "button";
    removeBtn.className = "button is-small is-danger removeRow";
    removeBtn.textContent = "X";
    actionCell.appendChild(removeBtn);

    row.appendChild(indexCell);
    row.appendChild(nameCell);
    row.appendChild(quantityCell);
    row.appendChild(noteCell);
    row.appendChild(priceCell);
    row.appendChild(actionCell);
    tableBody.appendChild(row);
    updateRowNumbers();
    calculateTotals();

    // reset inputs
    input.value = "";
    document.getElementById("drugQty").value = "";
    document.getElementById("drugNote").value = "";
    currentSelectedDrug = null;
    dropdown.style.display = "none";
  });

  tableBody.addEventListener("click", e => {
    if (e.target.classList.contains("removeRow")) {
      e.target.closest("tr").remove();
      updateRowNumbers();
      calculateTotals();
    }
  });
});

// Drug usage schedule input (hdsd thuốc)
document.addEventListener("DOMContentLoaded", () => {
  const drugNote = document.getElementById("drugNote");
  const suggestionsBox = document.getElementById("scheduleSuggestions");
  const hintBtn = document.getElementById("hintBtn");
  const hintBox = document.getElementById("hintBox");
  const labels = ["sáng", "trưa", "chiều", "tối"];
  let currentIndex = -1;

  function parseSchedule(bits) {
    let result = [];
    for (let i = 0; i < bits.length; i++) {
      if (bits[i] !== "0") {
        result.push(`${labels[i]} ${bits[i]}`);
      }
    }
    return result.join(" - ");
  }

  function generateCandidates(input) {
    const results = [];
    const len = input.length;

    if (len === 4) {
      results.push(parseSchedule(input));
    } else if (len < 4 && len > 0) {
      for (let shift = 0; shift <= 4 - len; shift++) {
        let padded = "0".repeat(shift) + input + "0".repeat(4 - len - shift);
        results.push(parseSchedule(padded));
      }
    }
    return results.slice(0, 10);
  }

  function showSuggestions(candidates) {
    suggestionsBox.innerHTML = "";
    currentIndex = -1;

    if (candidates.length === 0) {
      suggestionsBox.style.display = "none";
      return;
    }

    candidates.forEach((c, idx) => {
      const div = document.createElement("div");
      div.textContent = c;
      div.className = "dropdown-item";
      div.style.padding = "6px 10px";
      div.style.cursor = "pointer";

      div.addEventListener("click", () => {
        drugNote.value = c;
        suggestionsBox.style.display = "none";
      });

      suggestionsBox.appendChild(div);
    });

    suggestionsBox.style.display = "block";
  }

  drugNote.addEventListener("input", (e) => {
    const val = e.target.value.trim();

    if (/[a-zA-Z]/.test(val)) {
      suggestionsBox.style.display = "none";
      return;
    }

    const clean = val.replace(/[^0-9]/g, "");
    if (clean !== val) e.target.value = clean;

    const candidates = generateCandidates(clean);
    if (candidates.length === 1 && clean.length === 4) {
      e.target.value = candidates[0];
      suggestionsBox.style.display = "none";
    } else {
      showSuggestions(candidates);
    }
  });

  drugNote.addEventListener("keydown", (e) => {
    const items = suggestionsBox.querySelectorAll("div");
    if (items.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      currentIndex = (currentIndex + 1) % items.length;
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      currentIndex = (currentIndex - 1 + items.length) % items.length;
    } else if (e.key === "Enter") {
      if (currentIndex >= 0 && currentIndex < items.length) {
        e.preventDefault();
        drugNote.value = items[currentIndex].textContent;
        suggestionsBox.style.display = "none";
      }
    }

    items.forEach((item, idx) => {
      item.style.background = idx === currentIndex ? "#eee" : "white";
    });
  });

  if (hintBtn && hintBox) {
    hintBtn.addEventListener("click", () => {
      hintBox.style.display = hintBox.style.display === "none" ? "block" : "none";
    });
  }
  calculateTotals();
});

// Image preview before upload
// ── Image Gallery (new exam) ──────────────────────────────────────────────
// Files accumulate in pendingDT across multiple file-picker opens.
// On form submit the files are synced into FormData (see submit handler).
let pendingDT = new DataTransfer();

document.addEventListener("DOMContentLoaded", () => {
  const labImages = document.getElementById("lab_images");
  if (!labImages) return;

  document.getElementById("addImagesBtn").addEventListener("click", () => labImages.click());
  document.getElementById("clearAllImagesBtn").addEventListener("click", clearAllNewExamImages);

  labImages.addEventListener("change", function () {
    if (this.files.length) addNewExamFiles(this.files);
    this.value = ""; // reset so the same file can be re-selected after removal
  });

  // Modal close wiring
  document.getElementById("newExamModalBg").addEventListener("click", closeNewExamModal);
  document.getElementById("newExamModalClose").addEventListener("click", closeNewExamModal);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeNewExamModal(); });
});

function addNewExamFiles(fileList) {
  const gallery = document.getElementById("imageGallery");
  Array.from(fileList).forEach((file) => {
    // Skip exact duplicates already queued
    for (const existing of pendingDT.files) {
      if (existing.name === file.name && existing.size === file.size) return;
    }
    pendingDT.items.add(file);
    const reader = new FileReader();
    reader.onload = (e) => gallery.appendChild(buildNewExamThumb(file, e.target.result));
    reader.readAsDataURL(file);
  });
}

function buildNewExamThumb(file, dataUrl) {
  const wrapper = document.createElement("div");
  wrapper.style.cssText = "position:relative; display:inline-block;";
  wrapper.dataset.pendingName = file.name;

  const img = document.createElement("img");
  img.src = dataUrl;
  img.style.cssText = "height:150px; width:150px; object-fit:cover; border-radius:4px; border:2px dashed #3298dc; cursor:pointer;";
  img.title = file.name + " — click để phóng to";
  img.addEventListener("click", () => openNewExamModal(dataUrl));

  const delBtn = document.createElement("button");
  delBtn.type = "button";
  delBtn.className = "delete is-small";
  delBtn.style.cssText = "position:absolute; top:5px; right:5px;";
  delBtn.title = "Bỏ ảnh này";
  delBtn.addEventListener("click", (e) => { e.stopPropagation(); removeNewExamFile(file.name, wrapper); });

  wrapper.appendChild(img);
  wrapper.appendChild(delBtn);
  return wrapper;
}

function removeNewExamFile(filename, wrapperEl) {
  const newDT = new DataTransfer();
  for (const f of pendingDT.files) {
    if (f.name !== filename) newDT.items.add(f);
  }
  pendingDT = newDT;
  if (wrapperEl) wrapperEl.remove();
}

function clearAllNewExamImages() {
  pendingDT = new DataTransfer();
  const gallery = document.getElementById("imageGallery");
  if (gallery) gallery.innerHTML = "";
}

function openNewExamModal(src) {
  document.getElementById("newExamModalImg").src = src;
  document.getElementById("newExamImageModal").classList.add("is-active");
}

function closeNewExamModal() {
  document.getElementById("newExamImageModal").classList.remove("is-active");
  document.getElementById("newExamModalImg").src = "";
}
