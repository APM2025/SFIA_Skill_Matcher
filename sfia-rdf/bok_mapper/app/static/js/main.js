// Global state
let availableBoks = {};
let availableKas = {};
let selectedBok = '';
let selectedKa = '';
let currentResult = null;

document.addEventListener('DOMContentLoaded', () => {
    loadBoks();
    document.getElementById('bokSelect').addEventListener('change', onBokChange);
    document.getElementById('kaSelect').addEventListener('change', onKaChange);
    document.getElementById('mapBtn').addEventListener('click', mapToSfia);
    document.getElementById('exportBtn').addEventListener('click', exportResults);
});

function onBokChange() {
    selectedBok = document.getElementById('bokSelect').value;
    selectedKa = '';
    const kaSelect = document.getElementById('kaSelect');
    kaSelect.innerHTML = '<option value="">Select Knowledge Area...</option>';
    kaSelect.disabled = true;
    document.getElementById('kaInfo').classList.remove('show');
    document.getElementById('mapBtn').disabled = true;
    if (selectedBok) loadKnowledgeAreas(selectedBok);
}

function onKaChange() {
    selectedKa = document.getElementById('kaSelect').value;
    if (selectedKa) {
        displayKaInfo(selectedKa);
        document.getElementById('mapBtn').disabled = false;
    } else {
        document.getElementById('kaInfo').classList.remove('show');
        document.getElementById('mapBtn').disabled = true;
    }
}

function loadBoks() {
    fetch('/api/boks')
        .then(r => r.json())
        .then(data => {
            if (!data.success) return;
            availableBoks = data.boks;
            const select = document.getElementById('bokSelect');
            select.innerHTML = '<option value="">Select a Body of Knowledge...</option>';
            for (const [id, bok] of Object.entries(data.boks)) {
                const opt = document.createElement('option');
                opt.value = id;
                opt.textContent = bok.name;
                select.appendChild(opt);
            }
        })
        .catch(e => console.error('Error loading BoKs:', e));
}

function loadKnowledgeAreas(bokId) {
    fetch(`/api/boks/${bokId}/knowledge_areas`)
        .then(r => r.json())
        .then(data => {
            if (!data.success) return;
            availableKas = data.knowledge_areas;
            const select = document.getElementById('kaSelect');
            select.innerHTML = '<option value="">Select Knowledge Area...</option>';

            // Group by category
            const byCategory = {};
            for (const [id, ka] of Object.entries(data.knowledge_areas)) {
                const cat = ka.category || 'Other';
                if (!byCategory[cat]) byCategory[cat] = [];
                byCategory[cat].push({ id, ...ka });
            }
            for (const [cat, kas] of Object.entries(byCategory)) {
                const group = document.createElement('optgroup');
                group.label = cat;
                kas.forEach(ka => {
                    const opt = document.createElement('option');
                    opt.value = ka.id;
                    opt.textContent = `${ka.id} – ${ka.title} (${ka.chapter_count} chapters)`;
                    group.appendChild(opt);
                });
                select.appendChild(group);
            }
            select.disabled = false;
        })
        .catch(e => console.error('Error loading KAs:', e));
}

function displayKaInfo(kaId) {
    const ka = availableKas[kaId];
    if (!ka) return;
    document.getElementById('kaTitle').textContent = ka.title;
    document.getElementById('kaDescription').textContent = ka.description;
    const topicsList = document.getElementById('kaTopics');
    topicsList.innerHTML = '';
    ka.topics.forEach(t => {
        const li = document.createElement('li');
        li.textContent = t;
        topicsList.appendChild(li);
    });
    document.getElementById('kaInfo').classList.add('show');
}

function mapToSfia() {
    if (!selectedBok || !selectedKa) return;
    const cyberContext = document.getElementById('cyberContext').checked;
    document.getElementById('loading').classList.add('show');
    document.getElementById('mapBtn').disabled = true;

    fetch('/api/map', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bok_id: selectedBok, ka_id: selectedKa, cyber_context: cyberContext, top_k: 7 })
    })
        .then(r => r.json())
        .then(data => {
            document.getElementById('loading').classList.remove('show');
            document.getElementById('mapBtn').disabled = false;
            if (data.success) {
                currentResult = data.result;
                renderChapterMappings(currentResult);
                document.getElementById('exportBtn').style.display = 'inline-block';
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(e => {
            document.getElementById('loading').classList.remove('show');
            document.getElementById('mapBtn').disabled = false;
            console.error('Mapping error:', e);
            alert('An error occurred during mapping.');
        });
}

function renderChapterMappings(result) {
    const container = document.getElementById('skillMatches');
    const resultsDiv = document.getElementById('results');
    container.innerHTML = '';

    // KA header
    const header = document.createElement('div');
    header.innerHTML = `
        <h3 style="color:#1e293b; margin-bottom:4px;">${result.ka_id}: ${result.ka_title}</h3>
        <p style="color:#64748b; font-size:0.85rem; margin-bottom:20px;">${result.ka_category} · ${result.chapter_mappings.length} chapters mapped</p>
    `;
    container.appendChild(header);

    if (!result.chapter_mappings || result.chapter_mappings.length === 0) {
        container.innerHTML += '<p>No mappings found.</p>';
    } else {
        result.chapter_mappings.forEach((chapter, idx) => {
            const section = document.createElement('div');
            section.style.cssText = 'border:1px solid #e2e8f0; border-radius:10px; margin-bottom:16px; overflow:hidden;';

            const chapterHeader = document.createElement('div');
            chapterHeader.style.cssText = 'background:#f8fafc; padding:14px 18px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; user-select:none;';
            chapterHeader.innerHTML = `
                <div>
                    <span style="font-weight:700; color:#1e293b; font-size:0.95rem;">${chapter.chapter_id}: ${chapter.chapter_title}</span>
                    <div style="font-size:0.8rem; color:#64748b; margin-top:3px;">${chapter.chapter_description}</div>
                </div>
                <span class="toggle-icon" style="font-size:1.2rem; color:#6366f1; transition:transform 0.2s;" data-idx="${idx}">▾</span>
            `;

            const chapterBody = document.createElement('div');
            chapterBody.style.cssText = 'padding:16px 18px; display:block;';
            chapterBody.id = `chapter-body-${idx}`;

            chapter.sfia_mappings.forEach(match => {
                const matchDiv = document.createElement('div');
                matchDiv.className = 'skill-match';
                matchDiv.style.marginBottom = '10px';
                matchDiv.innerHTML = `
                    <div class="skill-header">
                        <div>
                            <span class="skill-name">${match.skill_name}</span>
                            <span class="skill-code">${match.skill_code}</span>
                        </div>
                        <div class="skill-score">${(match.competency_alignment * 100).toFixed(1)}%</div>
                    </div>
                    <div class="skill-description">${match.skill_description}</div>
                    <div style="margin-top:6px;">
                        <span class="skill-level"><strong>Suggested Level:</strong> ${match.suggested_level}</span>
                        <span class="skill-level"><strong>Confidence:</strong> ${(match.level_confidence * 100).toFixed(0)}%</span>
                    </div>
                `;
                chapterBody.appendChild(matchDiv);
            });

            // Toggle collapse
            chapterHeader.addEventListener('click', () => {
                const icon = chapterHeader.querySelector('.toggle-icon');
                if (chapterBody.style.display === 'none') {
                    chapterBody.style.display = 'block';
                    icon.style.transform = 'rotate(0deg)';
                } else {
                    chapterBody.style.display = 'none';
                    icon.style.transform = 'rotate(-90deg)';
                }
            });

            section.appendChild(chapterHeader);
            section.appendChild(chapterBody);
            container.appendChild(section);
        });
    }

    resultsDiv.classList.add('show');
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function exportResults() {
    if (!currentResult) return;
    const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `sfia_mapping_${selectedKa}_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}
