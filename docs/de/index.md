# eCH-0265 Landwirtschaftliche Kulturen

22. Juli 2026

- [Hinweis](#hinweis)
- [<span class="toc-section-number">1</span> Einleitung](#einleitung)
  - [<span class="toc-section-number">1.1</span> Status](#status)
  - [<span class="toc-section-number">1.2</span>
    Geltungsbereich](#geltungsbereich)
- [<span class="toc-section-number">2</span> Einführung](#einführung)
- [<span class="toc-section-number">3</span> Datenmodell](#datenmodell)
  - [<span class="toc-section-number">3.1</span>
    shape:CultivationType](#sec-shape-cultivationtype)
  - [<span class="toc-section-number">3.2</span>
    shape:CultivationType](#sec-shape-cultivationtype)
  - [<span class="toc-section-number">3.3</span>
    shape:DirectPaymentCrop](#sec-shape-directpaymentcrop)
  - [<span class="toc-section-number">3.4</span>
    shape:NutrientBalanceCrop](#sec-shape-nutrientbalancecrop)
  - [<span class="toc-section-number">3.5</span>
    shape:PlantProtectionCrop](#sec-shape-plantprotectioncrop)
- [<span class="toc-section-number">4</span>
  Sicherheitsaspekte](#sicherheitsaspekte)
- [<span class="toc-section-number">5</span>
  Haftungsausschluss](#haftungsausschluss)
- [<span class="toc-section-number">6</span>
  Urheberrechte](#urheberrechte)
- [<span class="toc-section-number">7</span> Anhang A -
  Referenzen](#anhang-a---referenzen)
- [<span class="toc-section-number">8</span> Anhang B - Mitwirkung &
  Prüfung](#anhang-b---mitwirkung--prüfung)
- [<span class="toc-section-number">9</span> Anhang C - Abkürzungen und
  Glossar](#anhang-c---abkürzungen-und-glossar)
- [<span class="toc-section-number">10</span> Anhang D - Änderungen
  gegenüber der
  Vorversion](#anhang-d---änderungen-gegenüber-der-vorversion)
- [<span class="toc-section-number">11</span> Anhang E -
  Abbildungsverzeichnis](#anhang-e---abbildungsverzeichnis)
- [<span class="toc-section-number">12</span> Anhang F -
  Tabellenverzeichnis](#anhang-f---tabellenverzeichnis)

# Hinweis

Im vorliegenden Dokument wird bei der Bezeichnung von Personen eine
geschlechtsneutrale Formulierung verwendet. Basis bildet der Leitfaden
der Bundeskanzlei. Je nach Situation kommen Paarformen (Bürgerinnen und
Bürger), geschlechtsabstrakte Formen (versicherte Person),
geschlechtsneutrale Formen (Versicherte) oder Umschreibungen ohne
Personenbezug zum Einsatz. Das generische Maskulin (Bürger) ist nicht
zulässig. Vollformen werden in fortlaufenden Texten verwendet, also in
Texten, die aus ausformulierten Sätzen bestehen. In verknappten
Textpassagen, namentlich in Tabellen, können Kurzformen verwendet
werden. Dabei wird die Kurzform mit Schrägstrich, aber ohne
Auslassungsstrich verwendet (Referent/in). Genderstern und ähnliche
Schreibweisen werden nicht verwendet.

# Einleitung

## Status

TODO

## Geltungsbereich

TODO

# Einführung

Das vorliegende Dokument ist ein Hilfsmittel zur harmonisierten,
systemübergreifenden Nutzung von landwirtschaftlichen Kulturdaten in der
Schweiz. Gegenüber der Version 1.1.0 (eCH-0265 Datenstandard Agrardaten
– Flächen und Kulturen) wurde das Dokument von einem unverbindlichen
Standard zu einem Hilfsmittel umgewandelt. Gleichzeitig wurde der
inhaltliche Fokus geschärft: Die Übertragung von Geometrien/Flächen[^1],
Sorten sowie Direktzahlungsprogrammen ist nicht mehr Teil dieses
Dokuments[^2]. Neu enthalten sind dafür die Kulturen aus dem
Pflanzenschutzmittelverzeichnis.

Im Zentrum der Version 2.0.0 stehen die Repräsentationen von
Kultur-Kategorien aus drei verschiedenen Bereichen (Direktzahlungen,
Nährstoffbilanz und Pflanzenschutz) im Zentrum. Das Hilfsmittel soll
dabei dienen, die Kulturen aus einem Bereich fachlich korrekt auf
diejenigen in einem anderen Bereich übersetzen zu können.

Dies wird über eine zentrale Ontologie erreicht, mit welcher die
landwirtschaftlichen Kulturen aus den verschiedenen Bereichen verbunden
sind. Damit schafft dieses Hilfsmittel eine zentrale Datenquelle, welche
in verschiedenen maschinenlesbaren Formaten über die LINDAS-Plattform in
Form von Linked Data bezogen werden kann.

# Datenmodell

## shape:CultivationType

**Zielklasse:** `:CultivationType`

<div id="tbl-shape-cultivationtype">

Tabelle 1: shape:CultivationType Eigenschaften

| Beschreibung | Pfad | Typ | Kardinalität |
|:---|:---|:---|---:|
| **Name** | `schema:name` | `rdf:langString` oder `sh:Literal` | 1..\* |
|  | `schema:alternateName` | `rdf:langString` oder `sh:Literal` | 0..\* |
| **Beschreibung** | `schema:description` | `rdf:langString` oder `sh:Literal` | 0..\* |
| **Bild** | `schema:image` | `sh:IRI` | 0..\* |
|  | `rdfs:subClassOf` | `sh:IRI` | 0..\* |
|  | `owl:intersectionOf` |  | 0..\* |
|  | `owl:unionOf` |  | 0..\* |
|  | `owl:disjointWith` | [:CultivationType](#sec-shape-cultivationtype) oder `sh:IRI` | 0..\* |
|  | `:botanicalPlant` | `sh:IRI` | 0..1 |
| **Anbauintensität** | `:managementIntensity` | `sh:IRI` | 0..1 |

</div>

## shape:CultivationType

**Zielklasse:** `:DeprecatedCultivationType`

<div id="tbl-shape-cultivationtype">

Tabelle 2: shape:CultivationType Eigenschaften

| Beschreibung | Pfad | Typ | Kardinalität |
|:---|:---|:---|---:|
| **Name** | `schema:name` | `rdf:langString` oder `sh:Literal` | 1..\* |
|  | `schema:alternateName` | `rdf:langString` oder `sh:Literal` | 0..\* |
| **Beschreibung** | `schema:description` | `rdf:langString` oder `sh:Literal` | 0..\* |
| **Bild** | `schema:image` | `sh:IRI` | 0..\* |
|  | `rdfs:subClassOf` | `sh:IRI` | 0..\* |
|  | `owl:intersectionOf` |  | 0..\* |
|  | `owl:unionOf` |  | 0..\* |
|  | `owl:disjointWith` | [:CultivationType](#sec-shape-cultivationtype) oder `sh:IRI` | 0..\* |
|  | `:botanicalPlant` | `sh:IRI` | 0..1 |
| **Anbauintensität** | `:managementIntensity` | `sh:IRI` | 0..1 |

</div>

## shape:DirectPaymentCrop

**Zielklasse:** `:DirectPaymentCrop`

<div id="tbl-shape-directpaymentcrop">

Tabelle 3: shape:DirectPaymentCrop Eigenschaften

| Beschreibung | Pfad | Typ | Kardinalität |
|:---|:---|:---|---:|
| **Identifikator**: Der LNF-Code, auch Kulturcode genannt, ist der allgemein gebräuchliche Identifikator für Direktzahlungskulturen in der Schweiz. | `schema:identifier` | `xsd:string` oder `sh:Literal` | 1..1 |
| **Bezeichnung** | `schema:name` | `rdf:langString` oder `sh:Literal` | 1..\* |
| **Kulturgruppe** | `:cultivationGroup` | [:CultivationType](#sec-shape-cultivationtype) oder `sh:IRI` | 0..1 |
| **Gültig von**: Ab welchem Jahr wurde diese Direktzahlungskultur offiziell verwendet? | `schema:validFrom` | `xsd:integer` oder `sh:Literal` | 0..1 |
| **Gültig bis**: Bis in welchem Jahr wurde diese Direktzahlungskultur offiziell verwendet? | `schema:validTo` |  | 0..1 |
| **Kultivierungstyp** | `:cultivationType` | [:CultivationType](#sec-shape-cultivationtype) | 0..1 |

</div>

## shape:NutrientBalanceCrop

**Zielklasse:** `:NutrientBalanceCrop`

<div id="tbl-shape-nutrientbalancecrop">

Tabelle 4: shape:NutrientBalanceCrop Eigenschaften

| Beschreibung | Pfad | Typ | Kardinalität |
|:---|:---|:---|---:|
| **Identifikator** | `schema:identifier` | `xsd:string` oder `sh:Literal` | 1..1 |
| **Bezeichnung** | `schema:name` | `rdf:langString` oder `sh:Literal` | 1..1 |
| **Kulturkategorie** | `:cultivationCategory` | [:CultivationType](#sec-shape-cultivationtype) oder `sh:IRI` | 1..1 |
| **Kultur-Unterkategorie** | `:cultivationSubCategory` | [:CultivationType](#sec-shape-cultivationtype) oder `sh:IRI` | 1..1 |
| **N**: Stickstoff, kg/ha | `:N2` | `xsd:decimal` oder `sh:Literal` | 0..1 |
| **P₂O₅**: Phosphor, kg/dt | `:P2O5` | `xsd:decimal` oder `sh:Literal` | 0..1 |
| **K₂O**: Kalium, kg/dt | `:K2O` | `xsd:decimal` oder `sh:Literal` | 0..1 |
| **Mg**: Magnesium, kg/dt | `:Mg` | `xsd:decimal` oder `sh:Literal` | 0..1 |
| **Kultivierungstyp** | `:cultivationType` | [:CultivationType](#sec-shape-cultivationtype) | 0..1 |

</div>

## shape:PlantProtectionCrop

**Zielklasse:** `:PlantProtectionCrop`

<div id="tbl-shape-plantprotectioncrop">

Tabelle 5: shape:PlantProtectionCrop Eigenschaften

| Beschreibung | Pfad | Typ | Kardinalität |
|:---|:---|:---|---:|
| **Identifikator** | `schema:identifier` | `xsd:string` oder `sh:Literal` | 1..1 |
| **Name**: Der in Infofito eingetragene Name dieser Kultur | `schema:name` | `sh:Literal` | 2..4 |
| **Version** | `schema:version` | `xsd:integer` oder `sh:Literal` | 1..1 |
| **Überkultur** | `schema:isPartOf` | [:PlantProtectionCrop](#sec-shape-plantprotectioncrop) oder `sh:IRI` | 0..2 |
| **Unterkultur** | `schema:hasPart` | [:PlantProtectionCrop](#sec-shape-plantprotectioncrop) oder `sh:IRI` | 0..\* |
| **Kultivierungstyp** | `:cultivationType` | [:CultivationType](#sec-shape-cultivationtype) | 0..1 |

</div>

# Sicherheitsaspekte

Informationen zu den ausdrücklich massgeblichen rechtlichen Grundlagen
oder ein Hinweis darauf, dass bei der Umsetzung die entsprechenden
rechtlichen Grundlagen zu beachten sind.

# Haftungsausschluss

eCH-Standards, die der Verein eCH dem Anwender kostenlos zur Verfügung
stellt oder die auf eCH verweisen, haben nur den Status von
Empfehlungen. Der Verein eCH haftet in keinem Fall für Entscheidungen
oder Massnahmen, die der Anwender auf der Grundlage dieser Dokumente
trifft bzw. ergreift. Der Anwender ist dafür verantwortlich, die
Dokumente vor ihrer Verwendung selbst zu überprüfen und gegebenenfalls
fachlichen Rat einzuholen. eCH-Standards können und sollen die
technische, organisatorische oder rechtliche Beratung im Einzelfall
nicht ersetzen.

Dokumente, Verfahren, Methoden, Produkte und Standards, auf die in
eCH-Standards verwiesen wird, sind möglicherweise durch Marken-,
Urheber- oder Patentrechte geschützt. Es liegt in der ausschliesslichen
Verantwortung des Anwenders, die erforderlichen Lizenzen von den
berechtigten Personen und/oder Organisationen einzuholen.

Obwohl der Verein eCH bei der Erstellung der eCH-Standards mit
angemessener Sorgfalt vorgegangen ist, kann er keine Gewährleistung oder
Garantie dafür übernehmen, dass die bereitgestellten Informationen und
Dokumente aktuell, vollständig, richtig oder fehlerfrei sind. eCH behält
sich das Recht vor, die Inhalte der eCH-Standards jederzeit und ohne
vorherige Ankündigung zu ändern.

Jede Haftung für Schäden, die durch die Nutzung der eCH-Standards durch
den Anwender entstehen, wird im gesetzlich zulässigen Rahmen
ausgeschlossen.

# Urheberrechte

Personen, die eCH-Standards erarbeiten, bleiben Inhaber ihrer geistigen
Eigentumsrechte. Diese Personen verpflichten sich jedoch, ihre geistigen
Eigentumsrechte oder andere Rechte an geistigen Eigentumsrechten
Dritter, soweit möglich, den jeweiligen Fachgruppen und dem Verein eCH
kostenlos und zur uneingeschränkten Nutzung und Weiterentwicklung im
Rahmen des Vereinszwecks zur Verfügung zu stellen.

Die von den Fachgruppen erarbeiteten Standards dürfen unter Nennung des
jeweiligen Autors von eCH kostenlos und in uneingeschränktem Umfang
genutzt, verbreitet und weiterentwickelt werden.

eCH-Standards sind vollständig dokumentiert und frei von lizenz-
und/oder patentrechtlichen Einschränkungen. Die dazugehörige
Dokumentation kann kostenlos angefordert werden. Diese Bestimmungen
gelten jedoch nur für die von eCH erarbeiteten Standards, nicht aber für
Standards oder Produkte Dritter, die auf eCH-Standards verweisen. Die
Standards enthalten die entsprechenden Hinweise auf Rechte Dritter.

# Anhang A - Referenzen

<div id="refs">

</div>

# Anhang B - Mitwirkung & Prüfung

# Anhang C - Abkürzungen und Glossar

# Anhang D - Änderungen gegenüber der Vorversion

# Anhang E - Abbildungsverzeichnis

# Anhang F - Tabellenverzeichnis

[^1]: Die Erhebung von landwirtschaftlichen Nutzflächen wird mit dem
    \[…\] spezifiziert.

[^2]: Eine spätere Wiederaufnahme von Sorten und Programmen bleibt
    vorbehalten.
