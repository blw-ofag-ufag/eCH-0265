mermaid.initialize({ 
    startOnLoad: false, 
    theme: 'default',
    state: { useMaxWidth: false }
});

const urlParams = new URLSearchParams(window.location.search);
const currentSystem = urlParams.get('system') || 'agis';

const systemDisplayTexts = {
    'agis': 'aus dem Agrarpolitischen Informationssystem AGIS',
    'naebi': 'der Suisse-Bilanz',
    'psm': 'aus dem Pflanzenschutzmittelverzeichnis'
};

const subtitleElement = document.querySelector('.subtitle');
if (subtitleElement) {
    const replacementText = systemDisplayTexts[currentSystem] || systemDisplayTexts['agis'];
    subtitleElement.innerHTML = subtitleElement.innerHTML.replace('__SYSTEM__', replacementText);
}

const systemLabels = {
    'agis': 'direct-payments',
    'naebi': 'nutrient-balance',
    'psm': 'plant-protection'
};
const githubSystemLabel = systemLabels[currentSystem] || 'data';

async function fetchOntologySource() {
    const rawUrl = 'https://raw.githubusercontent.com/blw-ofag-ufag/crops/main/rdf/ontology/cultivationtypes.ttl';
    try {
        const res = await fetch(rawUrl);
        if (!res.ok) throw new Error("Could not fetch ontology source.");
        return await res.text();
    } catch (e) {
        console.warn("Ontology fetch failed. Source Code links might lack exact line numbers.", e);
        return null;
    }
}

function getLineNumbers(rawText, slug) {
    if (!rawText || !slug) return null;
    
    const lines = rawText.split('\n');
    let startLine = -1;
    let endLine = -1;
    const searchPrefix = `cultivationtype:${slug} `;

    for (let i = 0; i < lines.length; i++) {
        if (startLine === -1 && lines[i].startsWith(searchPrefix)) {
            startLine = i + 1;
        }
        
        if (startLine !== -1 && i >= startLine - 1) {
            if (lines[i].trim().endsWith('.')) {
                endLine = i + 1;
                break;
            }
        }
    }

    if (startLine !== -1 && endLine !== -1) {
        return `L${startLine}-L${endLine}`;
    }
    return null;
}

async function fetchAndRenderData() {
    const endpointUrl = 'https://lindas.admin.ch/query';
    const appDiv = document.getElementById('app');

    try {
        const [queryRes, rawOntologyText] = await Promise.all([
            fetch('query.rq'),
            fetchOntologySource()
        ]);
        
        if (!queryRes.ok) throw new Error('Fehler beim Laden von query.rq.');
        let sparqlQuery = await queryRes.text();
        sparqlQuery = sparqlQuery.replace('{{SYSTEM_PREFIX}}', currentSystem);

        const response = await fetch(endpointUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/sparql-results+json'
            },
            body: 'query=' + encodeURIComponent(sparqlQuery)
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        await renderInterface(data.results.bindings, appDiv, rawOntologyText);

    } catch (error) {
        appDiv.innerHTML = `<div class="error"><strong>Fehler:</strong> ${error.message}</div>`;
    }
}

function getSafeId(uri) {
    if (!uri) return 'unknown';
    return 'node_' + uri.split('/').pop().replace(/[^a-zA-Z0-9]/g, '');
}

function formatNodeLabel(text) {
    if (!text) return 'Unknown';
    text = text.replace(/"/g, ''); 
    
    const MAX_TOTAL_LENGTH = 80;
    const MAX_LINE_LENGTH = 30;
    
    if (text.length > MAX_TOTAL_LENGTH) {
        text = text.substring(0, MAX_TOTAL_LENGTH).trim() + '...';
    }
    
    const words = text.split(' ');
    let lines = [];
    let currentLine = '';
    
    for (let word of words) {
        if ((currentLine + word).length > MAX_LINE_LENGTH) {
            if (currentLine) {
                lines.push(currentLine.trim());
            }
            currentLine = word + ' ';
        } else {
            currentLine += word + ' ';
        }
    }
    if (currentLine) {
        lines.push(currentLine.trim());
    }
    
    return lines.join('\\n');
}

function getGithubIssueUrl(cropName, slug) {
    const title = `Fehlermeldung zu "${cropName}" (cultivationtype:${slug})`;
    const body = `Ich habe einen Fehler bei der Kultur "${cropName}" (cultivationtype:${slug}) gefunden .\n\n## Fehlerbeschreibung\n\n[Was stimmt an der Taxonomie oder den Attributen nicht?]\n\n## Erwartetes Verhalten\n\n[Wie sollte es richtig sein?]`;
    const labels = `bug,data,${githubSystemLabel}`;
    
    const url = new URL('https://github.com/blw-ofag-ufag/crops/issues/new');
    url.searchParams.append('title', title);
    url.searchParams.append('body', body);
    url.searchParams.append('labels', labels);
    url.searchParams.append('template', 'bug.yml');
    
    return url.toString();
}

function getGithubSourceUrl(slug, rawText) {
    const baseUrl = 'https://github.com/blw-ofag-ufag/crops/blob/main/rdf/ontology/cultivationtypes.ttl';
    const lines = getLineNumbers(rawText, slug);
    return lines ? `${baseUrl}#${lines}` : baseUrl; 
}

async function renderInterface(bindings, container, rawOntologyText) {
    const cultivationTypes = {};
    const nodeNames = {};

    bindings.forEach(row => {
        const baseUri = row.CultivationType ? row.CultivationType.value : null;
        if (!baseUri) return;

        if (!cultivationTypes[baseUri]) {
            cultivationTypes[baseUri] = {
                baseUri: baseUri,
                baseName: row.BaseName ? row.BaseName.value : null,
                description: row.BaseDesc ? row.BaseDesc.value : null,
                altNames: new Set(),
                edges: new Set(),
                observations: [],
                // Initialize OWL Sets
                disjointNames: new Set(),
                unionNames: new Set(),
                intersectionNames: new Set()
            };
        }

        const ct = cultivationTypes[baseUri];

        if (row.BaseAltName) ct.altNames.add(row.BaseAltName.value);
        if (row.DisjointName) ct.disjointNames.add(row.DisjointName.value);
        if (row.UnionName) ct.unionNames.add(row.UnionName.value);
        if (row.IntersectionName) ct.intersectionNames.add(row.IntersectionName.value);
        
        if (row.Step && row.NextStep) {
            const stepUri = row.Step.value;
            const nextUri = row.NextStep.value;
            
            nodeNames[stepUri] = row.StepName ? row.StepName.value : stepUri;
            nodeNames[nextUri] = row.NextStepName ? row.NextStepName.value : nextUri;
            
            ct.edges.add(`${stepUri}|${nextUri}`);
        }

        const ident = row.Identifier ? row.Identifier.value : null;
        if (ident && !ct.observations.find(o => o.ident === ident)) {
            let validFromVal = row.ValidFrom ? row.ValidFrom.value : null;
            if (validFromVal === "https://cube.link/Undefined") validFromVal = null;

            let validToVal = row.ValidTo ? row.ValidTo.value : null;
            if (validToVal === "https://cube.link/Undefined") validToVal = null;

            ct.observations.push({
                ident: ident,
                crop: row.Crop ? row.Crop.value : null,
                validFrom: validFromVal,
                validTo: validToVal
            });
        }
    });

    container.innerHTML = '';

    if (Object.keys(cultivationTypes).length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--text-muted);">Keine Resultate für System <strong>${currentSystem}</strong> gefunden.</div>`;
        return;
    }

    const sortedEntries = Object.entries(cultivationTypes).sort((a, b) => {
        const aSlugStr = a[1].baseUri.split('/').pop();
        const bSlugStr = b[1].baseUri.split('/').pop();
        
        const aInt = parseInt(aSlugStr, 10);
        const bInt = parseInt(bSlugStr, 10);

        if (!isNaN(aInt) && !isNaN(bInt)) return aInt - bInt;
        if (!isNaN(aInt)) return -1;
        if (!isNaN(bInt)) return 1;
        return aSlugStr.localeCompare(bSlugStr);
    });

    for (const [uri, ct] of sortedEntries) {
        const card = document.createElement('div');
        card.className = 'card';

        const slug = ct.baseUri.split('/').pop();
        const mainName = ct.baseName || (ct.observations.length > 0 ? ct.observations[0].crop : 'Unbekannte Kultur'); 
        
        const githubIssueUrl = getGithubIssueUrl(mainName, slug);
        const githubSourceUrl = getGithubSourceUrl(slug, rawOntologyText);

        const buttonsContainer = `
            <div class="action-buttons">
                <a href="${githubSourceUrl}" target="_blank" class="action-btn" title="Quellcode ansehen">
                    <i class="bi bi-github"></i>
                </a>
                <a href="${githubIssueUrl}" target="_blank" class="action-btn" title="Fehler auf GitHub melden">
                    <i class="bi bi-bug-fill"></i>
                </a>
            </div>`;
        card.innerHTML += buttonsContainer;

        const textPanel = document.createElement('div');
        textPanel.className = 'text-panel';

        let displayIri = ct.baseUri;
        const segments = ct.baseUri.split('/').filter(Boolean);
        if (segments.length >= 2) {
            displayIri = `${segments[segments.length - 2]}:${segments[segments.length - 1]}`;
        }

        let textHTML = `<div class="main-title-row">`;
        textHTML += `<a href="${ct.baseUri}" target="_blank" class="crop-iri">${displayIri}</a>`;
        textHTML += `<h2 class="crop-name">${mainName}</h2>`;
        textHTML += `</div>`;

        if (ct.altNames.size > 0) {
            const altString = Array.from(ct.altNames).join(', ');
            textHTML += `<div class="alt-names">${altString}</div>`;
        }

        if (ct.description) {
            textHTML += `<div class="description">${ct.description}</div>`;
        }

        if (ct.unionNames.size > 0) {
            textHTML += `
                <div class="owl-info union">
                    <strong>Vereinigung von:</strong> 
                    ${Array.from(ct.unionNames).join(', ')}
                </div>`;
        }
        
        if (ct.intersectionNames.size > 0) {
            textHTML += `
                <div class="owl-info intersection">
                    <strong>Schnittmenge von:</strong> 
                    ${Array.from(ct.intersectionNames).join(', ')}
                </div>`;
        }
        
        if (ct.disjointNames.size > 0) {
            textHTML += `
                <div class="owl-info disjoint">
                    <strong>Disjunkt mit:</strong> 
                    ${Array.from(ct.disjointNames).join(', ')}
                </div>`;
        }

        let attrsContainerHTML = `<div class="attributes-container">`;
        
        ct.observations.forEach(obs => {
            const hasDifferentNames = ct.baseName && ct.baseName !== obs.crop;
            let attrsHTML = `<div class="attributes">`;
            attrsHTML += `<div class="attr-header">Attribute der Kultur im Quellsystem</div>`;
            
            let hasAttributes = false;
            
            if (obs.ident) {
                hasAttributes = true;
                attrsHTML += `
                    <div class="attr-row">
                        <div class="attr-key">Identifikator</div>
                        <div class="attr-val">${obs.ident}</div>
                    </div>`;
            }
            if (hasDifferentNames) {
                hasAttributes = true;
                attrsHTML += `
                    <div class="attr-row">
                        <div class="attr-key">Originalname</div>
                        <div class="attr-val">${obs.crop}</div>
                    </div>`;
            }
            if (obs.validFrom) {
                hasAttributes = true;
                attrsHTML += `
                    <div class="attr-row">
                        <div class="attr-key">Gültig von</div>
                        <div class="attr-val">${obs.validFrom}</div>
                    </div>`;
            }
            if (obs.validTo) {
                hasAttributes = true;
                attrsHTML += `
                    <div class="attr-row">
                        <div class="attr-key">Gültig bis</div>
                        <div class="attr-val">${obs.validTo}</div>
                    </div>`;
            }
            
            attrsHTML += `</div>`;
            if (hasAttributes) attrsContainerHTML += attrsHTML;
        });
        
        attrsContainerHTML += `</div>`;
        textHTML += attrsContainerHTML;
        
        textPanel.innerHTML = textHTML;
        card.appendChild(textPanel);

        if (ct.edges.size > 0) {
            const involvedUris = new Set();
            const edgeSources = new Set();
            const edgeTargets = new Set();

            ct.edges.forEach(edge => {
                const [source, target] = edge.split('|');
                involvedUris.add(source);
                involvedUris.add(target);
                edgeSources.add(source);
                edgeTargets.add(target);
            });

            const startNodes = new Set([...involvedUris].filter(uri => !edgeTargets.has(uri)));
            const endNodes = new Set([...involvedUris].filter(uri => !edgeSources.has(uri)));

            const intermediateNodes = [...involvedUris].filter(uri => !startNodes.has(uri) && !endNodes.has(uri));

            if (intermediateNodes.length > 0) {
                const graphPanel = document.createElement('div');
                graphPanel.className = 'graph-panel';

                let mermaidSyntax = "stateDiagram-v2\n    direction TB\n";

                intermediateNodes.forEach(uri => {
                    const id = getSafeId(uri);
                    const label = formatNodeLabel(nodeNames[uri]);
                    mermaidSyntax += `    state "${label}" as ${id}\n`;
                });

                ct.edges.forEach(edge => {
                    const [source, target] = edge.split('|');
                    
                    const sourceStr = startNodes.has(source) ? '[*]' : getSafeId(source);
                    const targetStr = endNodes.has(target) ? '[*]' : getSafeId(target);
                    
                    mermaidSyntax += `    ${sourceStr} --> ${targetStr}\n`;
                });

                const mermaidDiv = document.createElement('div');
                mermaidDiv.className = 'mermaid';
                mermaidDiv.textContent = mermaidSyntax;
                graphPanel.appendChild(mermaidDiv);
                
                card.appendChild(graphPanel);
            }
        }

        container.appendChild(card);
    }

    try {
        await mermaid.run({ querySelector: '.mermaid' });
    } catch (err) {
        console.error("Mermaid rendering failed:", err);
    }
}

fetchAndRenderData();