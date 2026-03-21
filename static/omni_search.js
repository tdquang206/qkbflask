/* omni_search.js — homepage live search behaviour */

(function () {
    'use strict';

    const input       = document.getElementById('omniSearchInput');
    const status      = document.getElementById('searchStatus');
    const summary     = document.getElementById('resultsSummary');
    const headline    = document.getElementById('resultsHeadline');
    const loading     = document.getElementById('loadingState');
    const empty       = document.getElementById('emptyState');
    const grid        = document.getElementById('resultsGrid');

    const GROUP_LABELS = {
        patients:  'Bệnh nhân',
        exams:     'Toa khám',
        drugs:     'Thuốc',
        mua_thuoc: 'Mua thuốc',
    };

    let debounceTimer  = null;
    let activeRequest  = null;   // AbortController for in-flight fetch

    /* ------------------------------------------------------------------ */
    /* Helpers                                                               */
    /* ------------------------------------------------------------------ */

    function escHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function setLoading(on) {
        loading.hidden = !on;
        status.textContent = on
            ? 'Đang tra cứu toàn bộ DB...'
            : 'Live search sau 3 ký tự, delay 500ms.';
    }

    function resetResults() {
        grid.innerHTML   = '';
        summary.hidden   = true;
        empty.hidden     = false;
        empty.textContent = 'Nhập ít nhất 3 ký tự để bắt đầu tra cứu nhanh.';
        setLoading(false);
    }

    /* ------------------------------------------------------------------ */
    /* Rendering                                                             */
    /* ------------------------------------------------------------------ */

    function buildCard(item) {
        const chips = (item.meta || [])
            .map(m => `<span class="search-chip">${escHtml(m)}</span>`)
            .join('');

        const secondaryBtn = item.secondary_action
            ? `<a class="button is-dark is-outlined is-small"
                  href="${escHtml(item.secondary_action.url)}">
                 ${escHtml(item.secondary_action.label)}
               </a>`
            : '';

        return `
            <article class="search-card">
                <div class="search-card-head">
                    <div>
                        <h3>${escHtml(item.title)}</h3>
                        <div class="search-subtitle">${escHtml(item.subtitle)}</div>
                    </div>
                </div>
                <div class="search-meta">${chips}</div>
                <p class="search-snippet">${escHtml(item.snippet)}</p>
                <div class="search-note">${escHtml(item.note)}</div>
                <div class="search-actions">
                    <a class="button is-primary is-small"
                       href="${escHtml(item.primary_action.url)}">
                        ${escHtml(item.primary_action.label)}
                    </a>
                    ${secondaryBtn}
                </div>
            </article>`;
    }

    function renderGroups(groups, totals) {
        const sections = Object.entries(GROUP_LABELS)
            .filter(([key]) => (groups[key] || []).length > 0)
            .map(([key, label]) => `
                <section class="search-group">
                    <div class="search-group-header">
                        <h2 class="search-group-title">${escHtml(label)}</h2>
                        <span class="search-group-count">${totals[key] || 0} kết quả</span>
                    </div>
                    <div class="search-card-list">
                        ${(groups[key] || []).map(buildCard).join('')}
                    </div>
                </section>`);

        grid.innerHTML = sections.join('');
    }

    /* ------------------------------------------------------------------ */
    /* Search execution                                                      */
    /* ------------------------------------------------------------------ */

    async function runSearch(query) {
        if (query.trim().length < 3) {
            if (activeRequest) activeRequest.abort();
            resetResults();
            return;
        }

        if (activeRequest) activeRequest.abort();
        activeRequest = new AbortController();

        setLoading(true);
        empty.hidden = true;

        try {
            const res  = await fetch(
                `/api/omni-search?q=${encodeURIComponent(query)}`,
                { signal: activeRequest.signal }
            );
            const data = await res.json();

            setLoading(false);

            const total = Object.values(data.totals || {})
                .reduce((s, n) => s + n, 0);

            summary.hidden = false;

            if (!data.has_results || !total) {
                grid.innerHTML   = '';
                headline.textContent = `Không thấy kết quả phù hợp cho "${query}".`;
                empty.hidden     = false;
                empty.textContent = 'Thử thêm số điện thoại, địa chỉ, tên thuốc, mã toa hoặc ghi chú gần đúng.';
                return;
            }

            headline.textContent = `Tìm thấy ${total} kết quả cho "${query}".`;
            empty.hidden = true;
            renderGroups(data.groups || {}, data.totals || {});

        } catch (err) {
            if (err.name === 'AbortError') return;
            setLoading(false);
            summary.hidden   = true;
            grid.innerHTML   = '';
            empty.hidden     = false;
            empty.textContent = 'Không thể tải kết quả. Kiểm tra kết nối rồi thử lại.';
        }
    }

    /* ------------------------------------------------------------------ */
    /* Event listeners                                                       */
    /* ------------------------------------------------------------------ */

    input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => runSearch(this.value), 500);
    });

    // Allow pressing Enter to bypass the debounce
    input.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        clearTimeout(debounceTimer);
        runSearch(this.value);
    });
}());
