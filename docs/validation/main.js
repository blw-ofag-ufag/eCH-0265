const ORG = 'blw-ofag-ufag';
const REPO = 'crops';
const BRANCH = 'main';
const CULTIVATIONTYPES = `https://raw.githubusercontent.com/${ORG}/${REPO}/${BRANCH}/rdf/ontology/cultivationtypes.ttl`;
const ENDPOINT = 'https://lindas.admin.ch/query';

mermaid.initialize({ 
    startOnLoad: false, 
    theme: 'base',
    themeVariables: {
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        fontSize: '14px',
        primaryColor: '#ffffff',       // Weisser Hintergrund für Boxen
        primaryTextColor: '#111827',   // Dunkelgrauer Text
        primaryBorderColor: '#111827', // Heller Rand wie bei den Karten
        lineColor: '#9ca3af',          // Mittelgraue Pfeile
        tertiaryColor: '#f9fafb'       // Fallback für andere Elemente
    },
    flowchart: { 
        useMaxWidth: false,
        nodeSpacing: 20,
        rankSpacing: 30
    }
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
    try {
        const res = await fetch(CULTIVATIONTYPES);
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
    const appDiv = document.getElementById('app');

    try {
        const [queryRes, rawOntologyText] = await Promise.all([
            fetch('query.rq'),
            fetchOntologySource()
        ]);
        
        if (!queryRes.ok) throw new Error('Fehler beim Laden von query.rq.');
        let sparqlQuery = await queryRes.text();
        sparqlQuery = sparqlQuery.replace('{{SYSTEM_PREFIX}}', currentSystem);

        const response = await fetch(ENDPOINT, {
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
    const MAX_LINE_LENGTH = 20;
    
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
    
    return lines.join('<br/>');
}

function getGithubIssueUrl(cropName, slug) {
    const title = `Fehlermeldung zu "${cropName}" (cultivationtype:${slug})`;
    const body = `Ich habe einen Fehler bei der Kultur "${cropName}" (cultivationtype:${slug}) gefunden .\n\n## Fehlerbeschreibung\n\n[Was stimmt an der Taxonomie oder den Attributen nicht?]\n\n## Erwartetes Verhalten\n\n[Wie sollte es richtig sein?]`;
    const labels = `bug,data,${githubSystemLabel}`;
    
    const url = new URL(`https://github.com/${ORG}/${REPO}/issues/new`);
    url.searchParams.append('title', title);
    url.searchParams.append('body', body);
    url.searchParams.append('labels', labels);
    url.searchParams.append('template', 'bug.yml');
    
    return url.toString();
}

function getGithubSourceUrl(slug, rawText) {
    const baseUrl = CULTIVATIONTYPES ;
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
            const cultivationUri = 'https://agriculture.ld.admin.ch/crops/Cultivation';
            const filteredEdges = new Set();

            ct.edges.forEach(edge => {
                const [source, target] = edge.split('|');
                if (source !== cultivationUri && target !== cultivationUri) {
                    filteredEdges.add(edge);
                }
            });

            if (filteredEdges.size > 0) {
                const graphPanel = document.createElement('div');
                graphPanel.className = 'graph-panel';                
                const focusNodeUri = ct.baseUri;
                const coreNodes = new Set([focusNodeUri]);
                let changed = true;
                while(changed) {
                    changed = false;
                    filteredEdges.forEach(edge => {
                        const [child, parent] = edge.split('|');
                        if (coreNodes.has(child) && !coreNodes.has(parent)) {
                            coreNodes.add(parent);
                            changed = true;
                        }
                    });
                }

                const parentToChildren = {};
                filteredEdges.forEach(e => {
                    const [child, parent] = e.split('|');
                    if(!parentToChildren[parent]) parentToChildren[parent] = [];
                    parentToChildren[parent].push(child);
                });

                const MAX_CHILDREN = 6;
                const visibleNodes = new Set(coreNodes);
                const visibleEdges = new Set();
                const dummyEdges = new Set();
                const dummyNodes = {}; 
                const visited = new Set(coreNodes);
                filteredEdges.forEach(edge => {
                    const [child, parent] = edge.split('|');
                    if (coreNodes.has(child) && coreNodes.has(parent)) {
                        visibleEdges.add(edge);
                    }
                });

                let queue = Array.from(coreNodes);

                while(queue.length > 0) {
                    const current = queue.shift();
                    const children = parentToChildren[current] || [];

                    const coreChildren = children.filter(c => coreNodes.has(c));
                    const nonCoreChildren = children.filter(c => !coreNodes.has(c)).sort((a, b) => {
                        const labelA = nodeNames[a] || a;
                        const labelB = nodeNames[b] || b;
                        return labelA.localeCompare(labelB);
                    });
                    if (coreChildren.length + nonCoreChildren.length > MAX_CHILDREN) {
                        const availableForNonCore = Math.max(0, MAX_CHILDREN - coreChildren.length - 1);
                        for(let i = 0; i < availableForNonCore; i++) {
                            const c = nonCoreChildren[i];
                            visibleNodes.add(c);
                            visibleEdges.add(`${c}|${current}`);
                            if (!visited.has(c)) {
                                visited.add(c);
                                queue.push(c);
                            }
                        }
                        const hiddenCount = nonCoreChildren.length - availableForNonCore;
                        if (hiddenCount > 0) {
                            const dummyId = getSafeId(current) + '_dummy';
                            dummyNodes[dummyId] = `${hiddenCount} weitere...`;
                            dummyEdges.add(`${dummyId}|${current}`);
                        }

                    } else {
                        nonCoreChildren.forEach(c => {
                            visibleNodes.add(c);
                            visibleEdges.add(`${c}|${current}`);
                            if (!visited.has(c)) {
                                visited.add(c);
                                queue.push(c);
                            }
                        });
                    }
                }
                
                let mermaidSyntax = "flowchart BT\n";

                visibleNodes.forEach(uri => {
                    const id = getSafeId(uri);
                    let rawLabel = nodeNames[uri] || uri;
                    if (uri === ct.baseUri && ct.baseName) {
                        rawLabel = ct.baseName;
                    }
                    const label = formatNodeLabel(rawLabel);
                    
                    if (uri === ct.baseUri) {
                        mermaidSyntax += `    ${id}["${label}"]:::focusNode\n`;
                    } else {
                        mermaidSyntax += `    ${id}["${label}"]\n`;
                    }
                });

                // Dummy-Knoten rendern
                Object.entries(dummyNodes).forEach(([dummyId, label]) => {
                    mermaidSyntax += `    ${dummyId}["${label}"]:::dummyNode\n`;
                });

                // Reguläre Kanten
                visibleEdges.forEach(edge => {
                    const [source, target] = edge.split('|');
                    mermaidSyntax += `    ${getSafeId(source)} --> ${getSafeId(target)}\n`;
                });

                // Gestrichelte Kanten für zusammengefasste Knoten
                dummyEdges.forEach(edge => {
                    const [source, target] = edge.split('|');
                    mermaidSyntax += `    ${source} -.-> ${getSafeId(target)}\n`;
                });

                mermaidSyntax += `    classDef focusNode fill:#eff6ff,stroke:#3b82f6,stroke-width:2px,color:#1e40af;\n`;
                mermaidSyntax += `    classDef dummyNode fill:#f9fafb,stroke:#9ca3af,stroke-width:1px,stroke-dasharray: 5 5,color:#6b7280;\n`;

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