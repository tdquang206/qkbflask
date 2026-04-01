(function () {
	'use strict';

	// Current context for the diff modal
	let _currentDiffSource = '';
	let _currentDiffGroup = '';
	let _currentDiffLabel = '';
	let _currentDiffTime = '';

	/* ── Diff modal ─────────────────────────────────────────────────── */

	window.openDiffModal = function (el) {
		const source = el.dataset.source;
		const groupKey = el.dataset.group;
		const label = el.dataset.label;
		const displayTime = el.dataset.dt;
		_currentDiffSource = source;
		_currentDiffGroup = groupKey;
		_currentDiffLabel = label;
		_currentDiffTime = displayTime;

		document.getElementById('diffModalTitle').textContent = displayTime + ' (' + label + ')';
		document.getElementById('diffSummaryBar').style.display = 'none';
		document.getElementById('diffLoading').style.display = 'block';
		document.getElementById('diffError').style.display = 'none';
		document.getElementById('diffNoChanges').style.display = 'none';
		document.getElementById('diffContent').style.display = 'none';
		document.getElementById('diffRestoreBtn').style.display = 'none';
		document.getElementById('diffContent').innerHTML = '';

		document.getElementById('diffModal').classList.add('is-active');
		fetchDiff(source, groupKey);
	};

	window.closeDiffModal = function () {
		document.getElementById('diffModal').classList.remove('is-active');
	};

	async function fetchDiff(source, groupKey) {
		try {
			const resp = await fetch('/api/admin/checkpoint/diff', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ source: source, group_key: groupKey }),
			});
			const data = await resp.json();
			document.getElementById('diffLoading').style.display = 'none';

			if (!resp.ok || data.error) {
				showDiffError(data.error || 'Server error ' + resp.status);
				return;
			}
			renderDiff(data);
		} catch (err) {
			document.getElementById('diffLoading').style.display = 'none';
			showDiffError('Network error: ' + err.message);
		}
	}

	function showDiffError(msg) {
		const el = document.getElementById('diffError');
		el.textContent = msg;
		el.style.display = 'block';
	}

	function renderDiff(data) {
		const summary = data.summary || {};
		const diffs = data.diffs || [];

		// Summary bar
		document.getElementById('summaryChanged').textContent = summary.total_changed || 0;
		document.getElementById('summaryAdded').textContent = summary.total_added || 0;
		document.getElementById('summaryRemoved').textContent = summary.total_removed || 0;
		const filesEl = document.getElementById('summaryFiles');
		filesEl.textContent = (summary.files_compared || []).join(', ');
		document.getElementById('diffSummaryBar').style.display = '';

		const totalChanges = (summary.total_changed || 0) + (summary.total_added || 0) + (summary.total_removed || 0);
		if (totalChanges === 0) {
			document.getElementById('diffNoChanges').style.display = '';
			return;
		}

		// Restore button visible
		document.getElementById('diffRestoreBtn').style.display = '';

		const container = document.getElementById('diffContent');
		container.innerHTML = '';

		diffs.forEach(function (fileDiff) {
			if (fileDiff.error) {
				const errDiv = document.createElement('div');
				errDiv.className = 'notification is-danger is-light mb-3';
				errDiv.textContent = fileDiff.db_file + ': ' + fileDiff.error;
				container.appendChild(errDiv);
				return;
			}
			if (!fileDiff.records || fileDiff.records.length === 0) return;

			const section = document.createElement('div');
			section.className = 'diff-file-section';

			// File header bar
			const header = document.createElement('div');
			header.className = 'diff-file-header-bar';
			header.innerHTML =
				'<span class="icon has-text-warning" style="margin-right:6px"><i class="fas fa-database"></i></span>' +
				'<span>' + escHtml(fileDiff.db_file) + '</span>' +
				(fileDiff.changed ? '<span class="count-badge">⚡ ' + fileDiff.changed + ' changed</span>' : '') +
				(fileDiff.added ? '<span class="count-badge ml-1">+ ' + fileDiff.added + ' added</span>' : '') +
				(fileDiff.removed ? '<span class="count-badge ml-1">- ' + fileDiff.removed + ' removed</span>' : '');
			section.appendChild(header);

			// Records
			fileDiff.records.forEach(function (rec, idx) {
				const recDiv = buildRecordDiv(rec, fileDiff.db_file + '_' + idx);
				section.appendChild(recDiv);
			});

			container.appendChild(section);
		});

		container.style.display = '';
	}

	function buildRecordDiv(rec, uid) {
		const recDiv = document.createElement('div');
		recDiv.className = 'diff-record';

		const headerDiv = document.createElement('div');
		headerDiv.className = 'diff-record-header';
		headerDiv.setAttribute('onclick', 'toggleRecord("body_' + uid + '", this)');

		const statusClass = { changed: 'status-changed', added: 'status-added', removed: 'status-removed' }[rec.status] || '';
		const statusText = { changed: '⚡ Changed', added: '+ Added', removed: '− Removed' }[rec.status] || rec.status;

		headerDiv.innerHTML =
			'<span class="status-badge ' + statusClass + '">' + statusText + '</span>' +
			'<span class="has-text-grey is-size-7" style="font-family:monospace">' + escHtml(rec.key) + '</span>' +
			'<span class="has-text-weight-semibold">' + escHtml(rec.label || '') + '</span>' +
			(rec.diff_lines && rec.diff_lines.length > 0 ? '<span class="toggle-icon">▼</span>' : '');

		recDiv.appendChild(headerDiv);

		if (rec.diff_lines && rec.diff_lines.length > 0) {
			const bodyDiv = document.createElement('div');
			bodyDiv.className = 'diff-record-body';
			bodyDiv.id = 'body_' + uid;

			const pre = document.createElement('pre');
			pre.className = 'diff-view';

			rec.diff_lines.forEach(function (line) {
				const span = document.createElement('span');
				span.className = 'diff-line ' + classifyLine(line);
				span.textContent = line;
				pre.appendChild(span);
			});

			if (rec.truncated) {
				const note = document.createElement('div');
				note.className = 'truncate-note';
				note.textContent = '… truncated. Showing 300 of ' + rec.total_lines + ' lines. Full diff available in the checkpoint files.';
				bodyDiv.appendChild(pre);
				bodyDiv.appendChild(note);
			} else {
				bodyDiv.appendChild(pre);
			}

			recDiv.appendChild(bodyDiv);
		}

		return recDiv;
	}

	window.toggleRecord = function (bodyId, headerEl) {
		const body = document.getElementById(bodyId);
		if (!body) return;
		const isOpen = body.classList.toggle('is-open');
		const icon = headerEl.querySelector('.toggle-icon');
		if (icon) icon.textContent = isOpen ? '▲' : '▼';
	};

	function classifyLine(line) {
		if (line.startsWith('+++') || line.startsWith('---')) return 'diff-line-file';
		if (line.startsWith('@@')) return 'diff-line-hunk';
		if (line.startsWith('+')) return 'diff-line-add';
		if (line.startsWith('-')) return 'diff-line-remove';
		return 'diff-line-ctx';
	}

	/* ── Restore confirm modal ──────────────────────────────────────── */

	window.openRestoreConfirm = function (el) {
		const source = el.dataset.source;
		const groupKey = el.dataset.group;
		const label = el.dataset.label;
		const displayTime = el.dataset.dt;
		_currentDiffSource = source;
		_currentDiffGroup = groupKey;
		_currentDiffLabel = label;
		_currentDiffTime = displayTime;
		document.getElementById('restoreTag').textContent = label;
		document.getElementById('restoreTime').textContent = displayTime;
		document.getElementById('restoreConfirmCheck').checked = false;
		document.getElementById('doRestoreBtn').disabled = true;
		document.getElementById('restoreModal').classList.add('is-active');
	};

	window.openRestoreFromDiff = function () {
		closeDiffModal();
		document.getElementById('restoreTag').textContent = _currentDiffLabel;
		document.getElementById('restoreTime').textContent = _currentDiffTime;
		document.getElementById('restoreConfirmCheck').checked = false;
		document.getElementById('doRestoreBtn').disabled = true;
		document.getElementById('restoreModal').classList.add('is-active');
	};

	window.closeRestoreModal = function () {
		document.getElementById('restoreModal').classList.remove('is-active');
	};

	window.toggleRestoreBtn = function () {
		const checked = document.getElementById('restoreConfirmCheck').checked;
		document.getElementById('doRestoreBtn').disabled = !checked;
	};

	window.executeRestore = async function () {
		const btn = document.getElementById('doRestoreBtn');
		btn.classList.add('is-loading');
		btn.disabled = true;

		try {
			const resp = await fetch('/api/admin/checkpoint/restore', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					source: _currentDiffSource,
					group_key: _currentDiffGroup,
					confirm: true,
				}),
			});
			const data = await resp.json();
			closeRestoreModal();

			if (resp.ok && data.success) {
				showRestoreResult(true, data);
			} else {
				showRestoreResult(false, data);
			}
		} catch (err) {
			closeRestoreModal();
			showRestoreResult(false, { errors: [err.message] });
		}
	};

	function showRestoreResult(success, data) {
		const head = document.getElementById('restoreResultHead');
		const title = document.getElementById('restoreResultTitle');
		const body = document.getElementById('restoreResultBody');

		head.className = 'modal-card-head ' + (success ? 'has-background-success-light' : 'has-background-danger-light');
		title.className = 'modal-card-title ' + (success ? 'has-text-success' : 'has-text-danger');

		if (success) {
			title.textContent = '✅ Restore Complete';
			body.innerHTML =
				'<p>Restored successfully.</p>' +
				'<ul class="mt-2">' +
				(data.restored || []).map(function (f) { return '<li><code>' + escHtml(f) + '</code></li>'; }).join('') +
				'</ul>' +
				'<p class="mt-3 has-text-grey is-size-7">Pre-restore safety copy saved at <code>backups/pre_restore_safety/pre_restore_' + escHtml(data.safety_backup_ts || '') + '_*.json</code></p>' +
				'<p class="mt-2 has-text-warning"><strong>Click "Reload Page" to see the restored data.</strong></p>';
		} else {
			title.textContent = '❌ Restore Failed';
			const errs = (data.errors || []).concat(data.error ? [data.error] : []);
			body.innerHTML =
				'<p>Restore encountered errors:</p>' +
				'<ul class="mt-2">' + errs.map(function (e) { return '<li class="has-text-danger">' + escHtml(e) + '</li>'; }).join('') + '</ul>' +
				(data.restored && data.restored.length ? '<p class="mt-2 has-text-warning">Partially restored: ' + data.restored.join(', ') + '</p>' : '');
		}

		document.getElementById('restoreResultModal').classList.add('is-active');
	}

	/* ── Utilities ──────────────────────────────────────────────────── */

	function escHtml(str) {
		return String(str || '')
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;');
	}
})();
