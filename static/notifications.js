(function () {
  const toggleBtn = document.getElementById("toggleNotifications");
  const panel = document.getElementById("notificationPanel");
  const content = document.getElementById("notificationContent");
  if (!toggleBtn || !panel || !content) return;

  let panelOpen = false;
  const errorLog = [];

  toggleBtn.addEventListener("click", () => {
    panelOpen = !panelOpen;
    panel.style.right = panelOpen ? "0" : "-350px";
  });

  function renderErrorPanel() {
    content.innerHTML = "";
    errorLog.forEach(err => {
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(err, null, 2);
      const divider = document.createElement("hr");
      content.appendChild(pre);
      content.appendChild(divider);
    });
  }

  function renderWarnings(warnings) {
    content.innerHTML = "";

    warnings.forEach(note => {
      const box = document.createElement("div");
      box.className = "notification is-warning is-light mb-3";

      const link = document.createElement("a");
      link.href = note.edit_path || "#";
      link.textContent = note.message || `Check sell price for ${note.drug_name || 'drug'}`;
      link.style.cssText = "font-weight:700; color:#3273dc; display:block; text-decoration:none; margin-bottom:.35rem;";
      box.appendChild(link);

      const detail = document.createElement("div");
      detail.textContent = `Buy ${note.buy_price || '-'} vs sell ${note.sell_price || '-'}`;
      box.appendChild(detail);

      content.appendChild(box);
    });
  }

  window.showNotification = function (data) {
    if (!data) return;

    if (Array.isArray(data.notifications) && data.notifications.length) {
      renderWarnings(data.notifications);
      panel.style.right = "0";
      panelOpen = true;
      return;
    }

    if (data.status === "error") {
      errorLog.unshift(data);
      if (errorLog.length > 20) errorLog.pop();
      renderErrorPanel();
      panel.style.right = "0";
      panelOpen = true;
    }
  };

  (function () {
    const origFetch = window.fetch.bind(window);
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

    window.fetch = function (url, opts) {
      opts = opts || {};
      const method = (opts.method || 'GET').toUpperCase();

      if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        opts.headers = opts.headers || {};
        if (opts.headers instanceof Headers) {
          if (!opts.headers.has('X-CSRFToken') && csrfToken) opts.headers.set('X-CSRFToken', csrfToken);
        } else {
          if (!opts.headers['X-CSRFToken'] && csrfToken) opts.headers['X-CSRFToken'] = csrfToken;
        }
      }

      return origFetch(url, opts).then(async res => {
        try {
          const clone = res.clone();
          const data = await clone.json();
          showNotification(data);
        } catch (e) {
          // not JSON, ignore
        }
        return res;
      });
    };
  })();
})();
