let registrations = {};
let selectedFramework = '';
let selectedRegistration = '';
let selectedCompetency = '';
let currentValidation = null;
let currentMatches = null;

// Load frameworks on page load
document.addEventListener('DOMContentLoaded', function () {
    loadFrameworks();
});

// Export button handler
document.getElementById('exportBtn').addEventListener('click', function () {
    if (!currentMatches) return;

    const exportData = {
        timestamp: new Date().toISOString(),
        framework: selectedFramework,
        registration: selectedRegistration,
        competency: selectedCompetency,
        cyber_context: document.getElementById('cyberContext').checked,
        validation: currentValidation,
        matches: currentMatches
    };

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "framework_to_sfia_export.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
});

// Framework selection handler
document.getElementById('framework').addEventListener('change', function () {
    selectedFramework = this.value;
    if (selectedFramework) {
        loadRegistrations(selectedFramework);
    } else {
        document.getElementById('registration').disabled = true;
        document.getElementById('competency').disabled = true;
    }
});

// Registration selection handler
document.getElementById('registration').addEventListener('change', function () {
    selectedRegistration = this.value;
    if (selectedRegistration) {
        loadCompetencies(selectedRegistration);
    } else {
        document.getElementById('competency').disabled = true;
    }
});

// Competency selection handler
document.getElementById('competency').addEventListener('change', function () {
    selectedCompetency = this.value;
    if (selectedCompetency) {
        loadCompetencyDetails(selectedFramework, selectedRegistration, selectedCompetency);
        enableMapping();
    } else {
        document.getElementById('competencyInfo').classList.remove('show');
        disableMapping();
    }
});

// Map button handler
document.getElementById('mapBtn').addEventListener('click', mapToSfia);

// Load available frameworks
function loadFrameworks() {
    fetch('/api/frameworks')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const select = document.getElementById('framework');
                select.innerHTML = '<option value="">Select a framework...</option>';

                for (const [id, framework] of Object.entries(data.frameworks)) {
                    const option = document.createElement('option');
                    option.value = id;
                    option.textContent = framework.name;
                    select.appendChild(option);
                }
            }
        })
        .catch(error => console.error('Error loading frameworks:', error));
}

// Load registrations for selected framework
function loadRegistrations(frameworkId) {
    fetch(`/api/frameworks/${frameworkId}/registrations`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                registrations = data.registrations;
                const select = document.getElementById('registration');
                select.innerHTML = '<option value="">Select registration level...</option>';

                for (const [code, reg] of Object.entries(data.registrations)) {
                    const option = document.createElement('option');
                    option.value = code;
                    option.textContent = `${code} - ${reg.title}`;
                    select.appendChild(option);
                }

                select.disabled = false;
            }
        })
        .catch(error => console.error('Error loading registrations:', error));
}

// Load competencies for selected registration
function loadCompetencies(registrationCode) {
    const reg = registrations[registrationCode];
    if (reg && reg.competencies) {
        const select = document.getElementById('competency');
        select.innerHTML = '<option value="">Select competency...</option>';

        reg.competencies.forEach(code => {
            const option = document.createElement('option');
            option.value = code;
            option.textContent = `Competency ${code}`;
            select.appendChild(option);
        });

        select.disabled = false;
    }
}

// Load detailed information about selected competency
function loadCompetencyDetails(frameworkId, registrationCode, competencyCode) {
    fetch(`/api/frameworks/${frameworkId}/${registrationCode}/${competencyCode}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const comp = data.competency.competency;
                document.getElementById('competencyTitle').textContent = comp.title;
                document.getElementById('competencyDescription').textContent = comp.full_description;

                const indicators = document.getElementById('competencyIndicators');
                indicators.innerHTML = '';

                if (comp.sub_competencies) {
                    comp.sub_competencies.forEach(sc => {
                        const li = document.createElement('li');
                        li.innerHTML = `<strong>${sc.code}</strong>: ${sc.description}`;
                        indicators.appendChild(li);
                    });
                } else if (comp.indicators) {
                    comp.indicators.forEach(indicator => {
                        const li = document.createElement('li');
                        li.textContent = indicator;
                        indicators.appendChild(li);
                    });
                }

                document.getElementById('competencyInfo').classList.add('show');
            }
        })
        .catch(error => console.error('Error loading competency details:', error));
}

// Enable mapping when all required fields are set
function enableMapping() {
    if (selectedCompetency && selectedRegistration && selectedFramework) {
        document.getElementById('mapBtn').disabled = false;
    }
}

function disableMapping() {
    document.getElementById('mapBtn').disabled = true;
}

// Map to SFIA skills
function mapToSfia() {
    if (!selectedFramework || !selectedRegistration || !selectedCompetency) {
        alert('Please select a framework and competency to map.');
        return;
    }

    const isCyberContext = document.getElementById('cyberContext').checked;

    showLoading();

    fetch('/api/map', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            framework_id: selectedFramework,
            registration_code: selectedRegistration,
            competency_code: selectedCompetency,
            cyber_context: isCyberContext,
            top_k: 10
        })
    })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                currentValidation = data.result.validation;
                currentMatches = data.result.indicator_mappings;
                displaySfiaMatches(currentMatches);
                document.getElementById('exportBtn').style.display = 'inline-block';
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            hideLoading();
            console.error('Error:', error);
            alert('An error occurred during mapping');
        });
}

// Display validation result
function displayValidationResult(validation) {
    const resultDiv = document.getElementById('validationResult');
    resultDiv.className = 'validation-result show ' + validation.relevance;
    resultDiv.innerHTML = `
                <strong>${validation.relevance.toUpperCase()} Match (${(validation.match_score * 100).toFixed(1)}%)</strong><br>
                ${validation.feedback}
                ${validation.keyword_matches.length > 0 ? '<br><br><strong>Matched Keywords:</strong> ' + validation.keyword_matches.join(', ') : ''}
            `;
}

// Display SFIA skill matches
function displaySfiaMatches(indicatorMappings) {
    const container = document.getElementById('skillMatches');
    const resultsDiv = document.getElementById('results');

    if (!indicatorMappings || indicatorMappings.length === 0) {
        container.innerHTML = '<p>No SFIA skill matches found.</p>';
        resultsDiv.classList.add('show');
        return;
    }

    container.innerHTML = '';

    indicatorMappings.forEach(mapping => {
        const indicatorHeader = document.createElement('h3');
        indicatorHeader.className = 'indicator-header';
        indicatorHeader.style.marginTop = '30px';
        indicatorHeader.style.marginBottom = '15px';
        indicatorHeader.style.paddingBottom = '10px';
        indicatorHeader.style.borderBottom = '1px solid #e2e8f0';
        indicatorHeader.style.color = '#1e293b';
        indicatorHeader.innerHTML = `<strong>${mapping.indicator_id}:</strong> ${mapping.indicator_text}`;
        container.appendChild(indicatorHeader);

        if (mapping.sfia_mappings.length === 0) {
            const noMatches = document.createElement('p');
            noMatches.textContent = 'No SFIA skill matches found for this indicator.';
            container.appendChild(noMatches);
        } else {
            mapping.sfia_mappings.forEach((match, index) => {
                const matchDiv = document.createElement('div');
                matchDiv.className = 'skill-match';
                matchDiv.innerHTML = `
                    <div class="skill-header">
                        <div>
                            <span class="skill-name">${match.skill_name}</span>
                            <span class="skill-code">${match.skill_code}</span>
                        </div>
                        <div class="skill-score">${(match.overall_score * 100).toFixed(1)}%</div>
                    </div>
                    <div class="skill-description">${match.skill_description}</div>
                    <div>
                        <span class="skill-level"><strong>Suggested Level:</strong> ${match.suggested_level}</span>
                        <span class="skill-level"><strong>Confidence:</strong> ${(match.level_confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div class="score-breakdown">
                        <div class="score-item"><strong>Conceptual Semantic Match Score:</strong> ${(match.competency_alignment * 100).toFixed(1)}%</div>
                    </div>
                    <div class="skill-rationale">${match.rationale}</div>
                `;
                container.appendChild(matchDiv);
            });
        }
    });

    resultsDiv.classList.add('show');
    resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Show loading spinner
function showLoading() {
    document.getElementById('loading').classList.add('show');
    document.getElementById('mapBtn').disabled = true;
}

// Hide loading spinner
function hideLoading() {
    document.getElementById('loading').classList.remove('show');
    enableMapping();
}