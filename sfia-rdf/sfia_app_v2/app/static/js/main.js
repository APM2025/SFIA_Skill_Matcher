let matchResultsData = null; // Store for JSON export

document.addEventListener('DOMContentLoaded', () => {
    // Restore from localStorage if exists
    const savedEvidence = localStorage.getItem('sfia_evidence');
    if (savedEvidence) {
        try {
            const ev = JSON.parse(savedEvidence);
            if (ev.situation) document.getElementById('star_situation').value = ev.situation;
            if (ev.task) document.getElementById('star_task').value = ev.task;
            if (ev.action) document.getElementById('star_action').value = ev.action;
            if (ev.result) document.getElementById('star_result').value = ev.result;
            if (ev.level_context) document.getElementById('level_context').value = ev.level_context;
        } catch (e) { }
    }
});

document.getElementById('matchForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const situation = document.getElementById('star_situation').value;
    const task = document.getElementById('star_task').value;
    const action = document.getElementById('star_action').value;
    const result_text = document.getElementById('star_result').value;
    const level_context = document.getElementById('level_context').value;

    if (!action.trim()) {
        alert('Please fill in the Action field — this is required for skill matching.');
        return;
    }

    // Save to local storage
    localStorage.setItem('sfia_evidence', JSON.stringify({
        situation, task, action, result: result_text, level_context
    }));

    // Assemble the text shown in the document highlighter
    const evidence = [
        situation ? `Situation\n${situation}` : '',
        task ? `Task\n${task}` : '',
        `Action\n${action}`,
        result_text ? `Result\n${result_text}` : ''
    ].filter(Boolean).join('\n\n');

    window._starSituation = situation;
    window._starTask = task;
    window._starAction = action;
    window._starResult = result_text;
    window._starLevel = level_context;
    window._starEvidence = evidence;

    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        const response = await fetch('/match', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                situation,
                task,
                action,
                result: result_text,
                level_context
            })
        });

        const data = await response.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        matchResultsData = data; // For export
        renderMatches(data, evidence);
    } catch (err) {
        console.error(err);
        alert('Error processing request');
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
});

function renderMatches(data, evidence) {
    // --- Render List ---
    const list = document.getElementById('matches-list');
    list.innerHTML = '';

    if (data.best_fit_summary && typeof data.best_fit_summary === 'object') {
        const bfs = data.best_fit_summary;
        const text = `The best skill match is <strong>${bfs.label}</strong> at <strong>Level ${bfs.level}</strong>. ${bfs.explanation}`;
        const summaryDiv = document.createElement('div');
        summaryDiv.style.padding = '1.5rem';
        summaryDiv.style.marginBottom = '2rem';
        summaryDiv.style.backgroundColor = '#fdf4ff';
        summaryDiv.style.border = '2px solid #f0abfc';
        summaryDiv.style.borderRadius = '8px';
        summaryDiv.innerHTML = `<h3 style="margin-top:0; color:#86198f;">Conclusion</h3><p style="margin:0; font-size:1.1rem; font-weight:500;">${text}</p>`;
        list.appendChild(summaryDiv);
    }

    if (data.detected_level) {
        const bestLevelInfo = (data.level_breakdown || []).find(l => l.level === data.detected_level);
        const explanation = (bestLevelInfo && bestLevelInfo.snippet) ?
            `because your context stated: <em>"${bestLevelInfo.snippet}"</em>` : '';

        const levelMsg = document.createElement('div');
        levelMsg.style.padding = '1rem';
        levelMsg.style.marginBottom = '1rem';
        levelMsg.style.backgroundColor = '#f0f9ff';
        levelMsg.style.borderLeft = '4px solid #0ea5e9';
        levelMsg.innerHTML = `<strong>Context Analysis:</strong> We detected your responsibility description aligns best with <strong>Level ${data.detected_level}</strong> ${explanation}.`;
        list.appendChild(levelMsg);
    }

    (data.matches || []).forEach((match, idx) => {
        const div = document.createElement('div');
        div.className = 'result-item';
        const cardId = `card-${idx}`;

        let badges = `<span class="level-tag">Level ${match.level}</span>`;
        if (match.boost_reason) {
            badges += `<span class="level-tag" style="background-color: #dcfce7; color: #166534; margin-left: 0.5rem;" title="${match.boost_reason}">Match Boosted</span>`;
        }
        if (match.category) {
            badges += `<span class="level-tag" style="background-color: #f3e8ff; color: #6b21a8; margin-left: 0.5rem;">${match.category}</span>`;
        }

        div.innerHTML = `
            <div class="result-header">
                <div>
                    <span class="skill-name">${match.label} [${match.code}]</span>
                    ${badges}
                </div>
                <div style="text-align: right;">
                    <span class="score-badge">${(match.score * 100).toFixed(1)}% Match</span>
                </div>
            </div>
            <div class="justification">${match.description}</div>
            <!-- Explainability Section -->
            <div style="margin-top: 0.75rem; background: #fffbeb; padding: 1rem; border-radius: 4px; border: 1px solid #fcd34d;">
                <strong style="color: #b45309; margin-bottom: 0.5rem; display: block;">Why this match?</strong>
                <p style="font-size: 0.9rem; color: #b45309; margin-top: 0; margin-bottom: 0.75rem; line-height: 1.4;"><em><strong>Note:</strong> The ${(match.score * 100).toFixed(1)}% match score is calculated using your <strong>entire</strong> text. The highlighted snippet below is just the specific portion that resonated most strongly with this SFIA skill.</em></p>
                <ul style="margin: 0 0 0 1.2rem; padding: 0; font-size: 0.95rem; color: #92400e; display: flex; flex-direction: column; gap: 0.5rem;">
                    ${match.boost_reason ? `<li>${match.boost_reason}</li>` : ''}
                    <li><strong>Strongest contributing segment:</strong> <em>"${match.evidence_snippet || 'Alignment computed over full text body.'}"</em></li>
                    <li><strong>SFIA notes correlation:</strong> <em>"${match.notes || 'No specific activities noted.'}"</em></li>
                </ul>
            </div>
            <!-- Refine Panel -->
            <div style="margin-top: 0.75rem; border-top: 1px solid var(--border); padding-top: 0.75rem;">
                <button onclick="document.getElementById('refine-${cardId}').style.display='block'; this.style.display='none';"
                    style="background: none; border: none; color: #6366f1; font-size: 0.9rem; cursor: pointer; padding: 0; text-decoration: underline;">
                    Not quite right? Refine this match →
                </button>
                <div id="refine-${cardId}" style="display:none; margin-top: 0.5rem;">
                    <p style="font-size:0.85rem; color:#64748b; margin: 0 0 0.4rem 0;">
                        Describe what this evidence was actually about in one sentence, e.g. <em>"It was about structured investigation and diagnosing root causes, not governance."</em>
                    </p>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <input id="refine-input-${cardId}" type="text" placeholder="e.g. It was more about root cause investigation than governance..."
                            style="flex: 1; padding: 0.5rem 0.75rem; border: 1px solid var(--border); border-radius: 6px; font-size: 0.9rem;" />
                        <button onclick="refineMatch(document.getElementById('refine-input-${cardId}').value)"
                            style="padding: 0.5rem 1rem; background: #6366f1; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem;">
                            Re-match
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Hover logic to highlight evidence
        if (match.evidence_snippet && match.evidence_snippet !== "No specific sentence isolated.") {
            div.addEventListener('mouseenter', () => highlightSnippet(match.evidence_snippet));
            div.addEventListener('mouseleave', () => clearHighlight());
        }

        list.appendChild(div);
    });

    // Final string formatting for evidence baseline
    const evidenceContainer = document.getElementById('highlighted-evidence');
    evidenceContainer.textContent = evidence;
    window.baseEvidenceText = evidence; // Store for reset

    // --- Level Analysis Section ---
    const levelAnalysis = document.getElementById('level-analysis');
    if (data.level_breakdown && data.level_breakdown.length > 0) {
        let html = `<h3>Level Analysis</h3><div style="display: flex; gap: 1rem; margin-bottom: 1rem;">`;
        data.level_breakdown.forEach(l => {
            const isSelected = l.level === data.detected_level;
            const bg = isSelected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(37, 99, 235, 0.1)';
            const border = isSelected ? '#10b981' : '#bfdbfe';
            const levelColor = isSelected ? '#065f46' : '#1e40af';
            const scoreColor = isSelected ? '#059669' : '#3b82f6';
            const badge = isSelected ? `<div style="font-size: 0.72rem; color: #065f46; font-weight: 700; margin-bottom: 2px;">✓ Selected</div>` : '';

            // Build tooltip with score breakdown if available
            let tooltip = '';
            if (l.semantic_score !== undefined && l.keyword_score !== undefined) {
                tooltip = `title="Score Breakdown:\n• Semantic Match: ${(l.semantic_score * 100).toFixed(1)}%\n• Keyword Match: ${(l.keyword_score * 100).toFixed(1)}%\n• Combined: ${(l.score * 100).toFixed(1)}% (70% semantic + 30% keywords)"`;
            }

            html += `
                <div ${tooltip} style="background: ${bg}; padding: 0.5rem; border-radius: 8px; border: 1px solid ${border}; flex: 1; text-align: center; cursor: help;">
                    ${badge}
                    <div style="font-weight: bold; color: ${levelColor}; font-size: 1.1rem;">Level ${l.level}</div>
                    <div style="color: ${scoreColor};">${(l.score * 100).toFixed(1)}% Confidence</div>
                </div>
            `;
        });
        html += `</div>`;
        html += `<div style="font-size: 0.85rem; color: #6b7280; margin-top: 0.5rem; font-style: italic;">💡 Hover over each level to see the score breakdown (semantic matching + keyword detection)</div>`;
        levelAnalysis.innerHTML = html;
        levelAnalysis.style.display = 'block';
    }

    document.getElementById('results').style.display = 'block';
}

function highlightSnippet(snippet) {
    const container = document.getElementById('highlighted-evidence');
    if (!container || !window.baseEvidenceText) return;

    const baseText = window.baseEvidenceText;

    // Simple string replace for exact match index bounds
    const index = baseText.indexOf(snippet);
    if (index !== -1) {
        const before = baseText.substring(0, index);
        const matchHtml = `<span id="current-highlight" style="background-color: #fef08a; padding: 0.2rem 0; border-radius: 4px; border-bottom: 2px solid #eab308; transition: background-color 0.2s; box-shadow: 0 0 0 4px #fef08a;">${snippet}</span>`;
        const after = baseText.substring(index + snippet.length);
        container.innerHTML = before + matchHtml + after;

        // Auto-scroll the evidence panel to the highlighted snippet
        const highlightEl = document.getElementById('current-highlight');
        if (highlightEl) {
            highlightEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    } else {
        // Fallback if formatting prevents exact index match
        container.textContent = baseText;
    }
}

function clearHighlight() {
    const container = document.getElementById('highlighted-evidence');
    if (container && window.baseEvidenceText) {
        container.textContent = window.baseEvidenceText;
    }
}

function clearForm() {
    document.getElementById('star_situation').value = '';
    document.getElementById('star_task').value = '';
    document.getElementById('star_action').value = '';
    document.getElementById('star_result').value = '';
    document.getElementById('level_context').value = '';
    document.getElementById('results').style.display = 'none';
    document.getElementById('loading').style.display = 'none';
    document.getElementById('level-analysis').innerHTML = '';
    document.getElementById('matches-list').innerHTML = '';
    document.getElementById('highlighted-evidence').innerHTML = '<em style="color: #94a3b8;">Your submitted evidence will appear here. Hover over a matched skill to highlight the exact sentence that triggered it.</em>';
    window._starSituation = window._starTask = window._starAction = window._starResult = window._starLevel = window._starEvidence = window.baseEvidenceText = '';
    localStorage.removeItem('sfia_evidence');
}

async function refineMatch(clarification) {
    if (!clarification || !clarification.trim()) {
        alert('Please describe what the evidence was actually about first.');
        return;
    }

    const situation = window._starSituation || '';
    const task = window._starTask || '';
    const action = window._starAction || '';
    const result_text = window._starResult || '';
    const level_context = window._starLevel || '';

    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const resp = await fetch('/refine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ situation, task, action, result: result_text, level_context, clarification })
        });

        const data = await resp.json();
        if (data.error) { alert(data.error); return; }

        matchResultsData = data;
        const list = document.getElementById('matches-list');
        list.innerHTML = '';

        // Purple Refined banner
        const banner = document.createElement('div');
        banner.style.cssText = 'background:#ede9fe; border:2px solid #8b5cf6; border-radius:8px; padding:1rem; margin-bottom:1rem;';
        banner.innerHTML = `<strong style="color:#6d28d9;">⟳ Refined Match</strong> — re-ranked with clarification: <em>"${clarification}"</em>`;
        list.appendChild(banner);

        // Best fit summary
        if (data.best_fit_summary && typeof data.best_fit_summary === 'object') {
            const bfs = data.best_fit_summary;
            const text = `The best skill match is <strong>${bfs.label}</strong> at <strong>Level ${bfs.level}</strong>. ${bfs.explanation}`;
            const s = document.createElement('div');
            s.style.cssText = 'padding:1.5rem; margin-bottom:1rem; background:#fdf4ff; border:2px solid #f0abfc; border-radius:8px;';
            s.innerHTML = `<h3 style="margin-top:0;color:#86198f;">Conclusion</h3><p style="margin:0;font-size:1.1rem;font-weight:500;">${text}</p>`;
            list.appendChild(s);
        }

        // Render each refined match card with its own refine panel
        (data.matches || []).forEach((match, idx) => {
            const cid = `r-card-${idx}`;
            const card = document.createElement('div');
            card.className = 'result-item';
            let badges = `<span class="level-tag">Level ${match.level}</span>`;
            if (match.category) badges += `<span class="level-tag" style="background:#f3e8ff;color:#6b21a8;margin-left:.5rem;">${match.category}</span>`;
            card.innerHTML = `
                <div class="result-header">
                    <div><span class="skill-name">${match.label} [${match.code}]</span>${badges}</div>
                    <div><span class="score-badge">${(match.score * 100).toFixed(1)}% Match</span></div>
                </div>
                <div class="justification">${match.description}</div>
                <div style="margin-top:0.5rem;border-top:1px solid var(--border);padding-top:0.5rem;">
                    <button onclick="document.getElementById('${cid}').style.display='block';this.style.display='none';"
                        style="background:none;border:none;color:#6366f1;font-size:0.9rem;cursor:pointer;padding:0;text-decoration:underline;">
                        Still not right? Refine again →
                    </button>
                    <div id="${cid}" style="display:none;margin-top:0.5rem;">
                        <div style="display:flex;gap:0.5rem;align-items:center;">
                            <input id="${cid}-in" type="text" placeholder="Clarify further..."
                                style="flex:1;padding:0.5rem 0.75rem;border:1px solid var(--border);border-radius:6px;font-size:0.9rem;" />
                            <button onclick="refineMatch(document.getElementById('${cid}-in').value)"
                                style="padding:0.5rem 1rem;background:#6366f1;color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.9rem;">
                                Re-match
                            </button>
                        </div>
                    </div>
                </div>`;
            list.appendChild(card);
        });

        document.getElementById('results').style.display = 'block';

    } catch (err) {
        console.error(err);
        alert('Error processing refined match');
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
}

function exportToJson() {
    if (!matchResultsData) return;
    const dataStr = JSON.stringify(matchResultsData, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = "sfia_match_results.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
