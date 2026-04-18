/**
 * drugs_discord.js
 * Sends the drug price list as an ASCII table to Discord via the backend API.
 */

(function () {
  'use strict';

  function showToast(message, isError) {
    let toast = document.getElementById('discord-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'discord-toast';
      Object.assign(toast.style, {
        position: 'fixed',
        bottom: '1.5rem',
        right: '1.5rem',
        padding: '0.75rem 1.25rem',
        borderRadius: '8px',
        color: '#fff',
        fontWeight: '600',
        fontSize: '0.9rem',
        zIndex: '9999',
        boxShadow: '0 4px 15px rgba(0,0,0,0.4)',
        transition: 'opacity 0.3s ease',
      });
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.background = isError ? '#f14668' : '#00d1b2';
    toast.style.opacity = '1';
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(() => { toast.style.opacity = '0'; }, 3500);
  }

  function sendDrugsToDiscord(btn) {
    btn.disabled = true;
    const originalHtml = btn.innerHTML;
    btn.textContent = 'Sending...';

    fetch('/api/drugs/send_discord', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data };
        });
      })
      .then(function ({ ok, data }) {
        if (ok && data.success) {
          showToast('Sent ' + data.rows + ' drugs to Discord.', false);
        } else {
          showToast('Error: ' + (data.error || 'Unknown error'), true);
        }
      })
      .catch(function (err) {
        showToast('Network error: ' + err.message, true);
      })
      .finally(function () {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('sendDrugsDiscordBtn');
    if (btn) {
      btn.addEventListener('click', function () {
        sendDrugsToDiscord(btn);
      });
    }
  });
})();
