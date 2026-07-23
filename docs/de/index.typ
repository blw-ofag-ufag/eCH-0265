// Simple numbering for non-book documents
#let equation-numbering = "(1)"
#let callout-numbering = "1"
#let subfloat-numbering(n-super, subfloat-idx) = {
  numbering("1a", n-super, subfloat-idx)
}

// Theorem configuration for theorion
// Simple numbering for non-book documents (no heading inheritance)
#let theorem-inherited-levels = 0

// Theorem numbering format (can be overridden by extensions for appendix support)
// This function returns the numbering pattern to use
#let theorem-numbering(loc) = "1.1"

// Default theorem render function
#let theorem-render(prefix: none, title: "", full-title: auto, body) = {
  if full-title != "" and full-title != auto and full-title != none {
    strong[#full-title.]
    h(0.5em)
  }
  body
}
// Some definitions presupposed by pandoc's typst output.
#let content-to-string(content) = {
  if content.has("text") {
    content.text
  } else if content.has("children") {
    content.children.map(content-to-string).join("")
  } else if content.has("body") {
    content-to-string(content.body)
  } else if content == [ ] {
    " "
  }
}

#let horizontalrule = line(start: (25%,0%), end: (75%,0%))

#let endnote(num, contents) = [
  #stack(dir: ltr, spacing: 3pt, super[#num], contents)
]

#show terms.item: it => block(breakable: false)[
  #text(weight: "bold")[#it.term]
  #block(inset: (left: 1.5em, top: -0.4em))[#it.description]
]

// Some quarto-specific definitions.

#show raw.where(block: true): set block(
    fill: luma(230),
    width: 100%,
    inset: 8pt,
    radius: 2pt
  )

#let block_with_new_content(old_block, new_content) = {
  let fields = old_block.fields()
  let _ = fields.remove("body")
  if fields.at("below", default: none) != none {
    // TODO: this is a hack because below is a "synthesized element"
    // according to the experts in the typst discord...
    fields.below = fields.below.abs
  }
  block.with(..fields)(new_content)
}

#let empty(v) = {
  if type(v) == str {
    // two dollar signs here because we're technically inside
    // a Pandoc template :grimace:
    v.matches(regex("^\\s*$")).at(0, default: none) != none
  } else if type(v) == content {
    if v.at("text", default: none) != none {
      return empty(v.text)
    }
    for child in v.at("children", default: ()) {
      if not empty(child) {
        return false
      }
    }
    return true
  }

}

// Subfloats
// This is a technique that we adapted from https://github.com/tingerrr/subpar/
#let quartosubfloatcounter = counter("quartosubfloatcounter")

#let quarto_super(
  kind: str,
  caption: none,
  label: none,
  supplement: str,
  position: none,
  subcapnumbering: "(a)",
  body,
) = {
  context {
    let figcounter = counter(figure.where(kind: kind))
    let n-super = figcounter.get().first() + 1
    set figure.caption(position: position)
    [#figure(
      kind: kind,
      supplement: supplement,
      caption: caption,
      {
        show figure.where(kind: kind): set figure(numbering: _ => {
          let subfloat-idx = quartosubfloatcounter.get().first() + 1
          subfloat-numbering(n-super, subfloat-idx)
        })
        show figure.where(kind: kind): set figure.caption(position: position)

        show figure: it => {
          let num = numbering(subcapnumbering, n-super, quartosubfloatcounter.get().first() + 1)
          show figure.caption: it => block({
            num.slice(2) // I don't understand why the numbering contains output that it really shouldn't, but this fixes it shrug?
            [ ]
            it.body
          })

          quartosubfloatcounter.step()
          it
          counter(figure.where(kind: it.kind)).update(n => n - 1)
        }

        quartosubfloatcounter.update(0)
        body
      }
    )#label]
  }
}

// callout rendering
// this is a figure show rule because callouts are crossreferenceable
#show figure: it => {
  if type(it.kind) != str {
    return it
  }
  let kind_match = it.kind.matches(regex("^quarto-callout-(.*)")).at(0, default: none)
  if kind_match == none {
    return it
  }
  let kind = kind_match.captures.at(0, default: "other")
  kind = upper(kind.first()) + kind.slice(1)
  // now we pull apart the callout and reassemble it with the crossref name and counter

  // when we cleanup pandoc's emitted code to avoid spaces this will have to change
  let old_callout = it.body.children.at(1).body.children.at(1)
  let old_title_block = old_callout.body.children.at(0)
  let children = old_title_block.body.body.children
  let old_title = if children.len() == 1 {
    children.at(0)  // no icon: title at index 0
  } else {
    children.at(1)  // with icon: title at index 1
  }

  // TODO use custom separator if available
  // Use the figure's counter display which handles chapter-based numbering
  // (when numbering is a function that includes the heading counter)
  let callout_num = it.counter.display(it.numbering)
  let new_title = if empty(old_title) {
    [#kind #callout_num]
  } else {
    [#kind #callout_num: #old_title]
  }

  let new_title_block = block_with_new_content(
    old_title_block,
    block_with_new_content(
      old_title_block.body,
      if children.len() == 1 {
        new_title  // no icon: just the title
      } else {
        children.at(0) + new_title  // with icon: preserve icon block + new title
      }))

  align(left, block_with_new_content(old_callout,
    block(below: 0pt, new_title_block) +
    old_callout.body.children.at(1)))
}

// 2023-10-09: #fa-icon("fa-info") is not working, so we'll eval "#fa-info()" instead
#let callout(body: [], title: "Callout", background_color: rgb("#dddddd"), icon: none, icon_color: black, body_background_color: white) = {
  block(
    breakable: false, 
    fill: background_color, 
    stroke: (paint: icon_color, thickness: 0.5pt, cap: "round"), 
    width: 100%, 
    radius: 2pt,
    block(
      inset: 1pt,
      width: 100%, 
      below: 0pt, 
      block(
        fill: background_color,
        width: 100%,
        inset: 8pt)[#if icon != none [#text(icon_color, weight: 900)[#icon] ]#title]) +
      if(body != []){
        block(
          inset: 1pt, 
          width: 100%, 
          block(fill: body_background_color, width: 100%, inset: 8pt, body))
      }
    )
}


// syntax highlighting functions from skylighting:
/* Function definitions for syntax highlighting generated by skylighting: */
#let EndLine() = raw("\n")
#let Skylighting(fill: none, number: false, start: 1, sourcelines) = {
   let blocks = []
   let lnum = start - 1
   let bgcolor = rgb("#f1f3f5")
   for ln in sourcelines {
     if number {
       lnum = lnum + 1
       blocks = blocks + box(width: if start + sourcelines.len() > 999 { 30pt } else { 24pt }, text(fill: rgb("#aaaaaa"), [ #lnum ]))
     }
     blocks = blocks + ln + EndLine()
   }
   block(fill: bgcolor, width: 100%, inset: 8pt, radius: 2pt, blocks)
}
#let AlertTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let AnnotationTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let AttributeTok(s) = text(fill: rgb("#657422"),raw(s))
#let BaseNTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let BuiltInTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let CharTok(s) = text(fill: rgb("#20794d"),raw(s))
#let CommentTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let CommentVarTok(s) = text(style: "italic",fill: rgb("#5e5e5e"),raw(s))
#let ConstantTok(s) = text(fill: rgb("#8f5902"),raw(s))
#let ControlFlowTok(s) = text(weight: "bold",fill: rgb("#003b4f"),raw(s))
#let DataTypeTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let DecValTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let DocumentationTok(s) = text(style: "italic",fill: rgb("#5e5e5e"),raw(s))
#let ErrorTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let ExtensionTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let FloatTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let FunctionTok(s) = text(fill: rgb("#4758ab"),raw(s))
#let ImportTok(s) = text(fill: rgb("#00769e"),raw(s))
#let InformationTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let KeywordTok(s) = text(weight: "bold",fill: rgb("#003b4f"),raw(s))
#let NormalTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let OperatorTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let OtherTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let PreprocessorTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let RegionMarkerTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let SpecialCharTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let SpecialStringTok(s) = text(fill: rgb("#20794d"),raw(s))
#let StringTok(s) = text(fill: rgb("#20794d"),raw(s))
#let VariableTok(s) = text(fill: rgb("#111111"),raw(s))
#let VerbatimStringTok(s) = text(fill: rgb("#20794d"),raw(s))
#let WarningTok(s) = text(style: "italic",fill: rgb("#5e5e5e"),raw(s))



#let article(
  title: none,
  subtitle: none,
  authors: none,
  keywords: (),
  date: none,
  abstract-title: none,
  abstract: none,
  thanks: none,
  cols: 1,
  lang: "en",
  region: "US",
  font: none,
  fontsize: 11pt,
  title-size: 1.5em,
  subtitle-size: 1.25em,
  heading-family: none,
  heading-weight: "bold",
  heading-style: "normal",
  heading-color: black,
  heading-line-height: 0.65em,
  mathfont: none,
  codefont: none,
  linestretch: 1,
  sectionnumbering: none,
  linkcolor: none,
  citecolor: none,
  filecolor: none,
  toc: false,
  toc_title: none,
  toc_depth: none,
  toc_indent: 1.5em,
  doc,
) = {
  // Set document metadata for PDF accessibility
  set document(title: title, keywords: keywords)
  set document(
    author: authors.map(author => content-to-string(author.name)).join(", ", last: " & "),
  ) if authors != none and authors != ()
  set par(
    justify: true,
    leading: linestretch * 0.65em
  )
  set text(lang: lang,
           region: region,
           size: fontsize)
  set text(font: font) if font != none
  show math.equation: set text(font: mathfont) if mathfont != none
  show raw: set text(font: codefont) if codefont != none

  set heading(numbering: sectionnumbering)

  show link: set text(fill: rgb(content-to-string(linkcolor))) if linkcolor != none
  show ref: set text(fill: rgb(content-to-string(citecolor))) if citecolor != none
  show link: this => {
    if filecolor != none and type(this.dest) == label {
      text(this, fill: rgb(content-to-string(filecolor)))
    } else {
      text(this)
    }
   }

  let has-title-block = title != none or (authors != none and authors != ()) or date != none or abstract != none
  if has-title-block {
    place(
      top,
      float: true,
      scope: "parent",
      clearance: 4mm,
      block(below: 1em, width: 100%)[

        #if title != none {
          align(center, block(inset: 2em)[
            #set par(leading: heading-line-height) if heading-line-height != none
            #set text(font: heading-family) if heading-family != none
            #set text(weight: heading-weight)
            #set text(style: heading-style) if heading-style != "normal"
            #set text(fill: heading-color) if heading-color != black

            #text(size: title-size)[#title #if thanks != none {
              footnote(thanks, numbering: "*")
              counter(footnote).update(n => n - 1)
            }]
            #(if subtitle != none {
              parbreak()
              text(size: subtitle-size)[#subtitle]
            })
          ])
        }

        #if authors != none and authors != () {
          let count = authors.len()
          let ncols = calc.min(count, 3)
          grid(
            columns: (1fr,) * ncols,
            row-gutter: 1.5em,
            ..authors.map(author =>
                align(center)[
                  #author.name \
                  #author.affiliation \
                  #author.email
                ]
            )
          )
        }

        #if date != none {
          align(center)[#block(inset: 1em)[
            #date
          ]]
        }

        #if abstract != none {
          block(inset: 2em)[
          #text(weight: "semibold")[#abstract-title] #h(1em) #abstract
          ]
        }
      ]
    )
  }

  if toc {
    let title = if toc_title == none {
      auto
    } else {
      toc_title
    }
    block(above: 0em, below: 2em)[
    #outline(
      title: toc_title,
      depth: toc_depth,
      indent: toc_indent
    );
    ]
  }

  doc
}

#set table(
  inset: 6pt,
  stroke: none
)
#let brand-color = (:)
#let brand-color-background = (:)
#let brand-logo = (:)

#set page(
  paper: "us-letter",
  margin: (x: 1.25in, y: 1.25in),
  numbering: "1",
  columns: 1,
)

#show: doc => article(
  title: [eCH-0265 Landwirtschaftliche Kulturen],
  date: [23. Juli 2026],
  lang: "de",
  region: "CH",
  abstract: [Dieses Hilfsmittel beschreibt ein Datenmodell zu landwirtschaftlichen Kulturen der Schweiz in den Bereichen Direktzahlungen, Nährstoffbilanz und Pflanzenschutz. Es werden sowohl das Datenmodell, die effektiven Daten sowie Mapping-Tabellen bereitgestellt, um den Bezug zwischen den unterschiedlichen Bereichen herzustellen. Sämtliche Daten können als maschinenlesbare #emph[Linked Data] bezogen werden. Damit soll ein fachlich validierter Datenaustausch sowie die Mehrfachnutzung von Daten ermöglicht werden.

],
  abstract-title: "Zusammenfassung",
  sectionnumbering: "1.1.a",
  toc_title: [Inhaltsverzeichnis],
  toc_depth: 3,
  doc,
)

#heading(level: 1, numbering: none)[Hinweis]
<hinweis>
Im vorliegenden Dokument wird bei der Bezeichnung von Personen eine geschlechtsneutrale Formulierung verwendet. Basis bildet der Leitfaden der Bundeskanzlei. Je nach Situation kommen Paarformen (Bürgerinnen und Bürger), geschlechtsabstrakte Formen (versicherte Person), geschlechtsneutrale Formen (Versicherte) oder Umschreibungen ohne Personenbezug zum Einsatz. Das generische Maskulin (Bürger) ist nicht zulässig. Vollformen werden in fortlaufenden Texten verwendet, also in Texten, die aus ausformulierten Sätzen bestehen. In verknappten Textpassagen, namentlich in Tabellen, können Kurzformen verwendet werden. Dabei wird die Kurzform mit Schrägstrich, aber ohne Auslassungsstrich verwendet (Referent/in). Genderstern und ähnliche Schreibweisen werden nicht verwendet.

= Einleitung
<einleitung>
Die Definitionen für landwirtschaftliche Kulturen wurden historisch unabhängig voneinander für spezifische gesetzliche Aufträge und Systeme entwickelt. Die fehlende systemübergreifende Harmonisierung (mit einer #emph[Single Source of Truth]) erschwert jedoch die Informationsverarbeitung über jeweilige Systemgrenzen hinaus.

== Was ist eine Kultur?
<was-ist-eine-kultur>
Der Begriff der landwirtschaftlichen Kultur stützt sich in diesem Hilfsmittel massgeblich auf das Konzept #NormalTok("CultivationType"); aus der Vorversion #link("@eCH-0265:1.0.0")[eCH-0265 v1.0.0]. Eine Kultur definiert sich demnach als Kategorie beziehungsweise als Teil eines Kategorisierungssystems, welches die Art der Nutzung und Kultivierung eines bestimmten Stücks Land über einen definierten Zeitraum beschreibt.

Durch diese Definition ist die landwirtschaftliche Kultur strikt von der botanischen Pflanze abzugrenzen. Die botanische Systematik klassifiziert biologische Einzelindividuen. Die landwirtschaftliche Kultur hingegen typisiert keine Individuen, sondern spezifische Formen der Landnutzung. Es geht bei der Kultur folglich nicht um die biologische Pflanze an sich, sondern um die flächen- und zeitbezogene Bewirtschaftungsform, an welche die jeweiligen agronomischen, rechtlichen oder systemischen Eigenschaften geknüpft sind.

Dieses Hilfsmittel dient dem Verständnis der Kulturbegriffe aus drei unterschiedlichen Bereichen, in welchen Definitionen landwirtschaftlicher Kulturen unabhängig voneinander gemacht wurden:

- #link(<sec-direct-payments>)[Direktzahlungen]
- #link(<sec-nutrient-balance>)[Nährstoffbilanz]
- #link(<sec-plant-protection>)[Pflanzenschutz]

In den folgenden Unterkapiteln werden die Kategorisierungssysteme landwirtschaftlicher Kulturen dieser drei Bereiche im Detail beschrieben.

== Direktzahlungen
<sec-direct-payments>
Im Rahmen des Direktzahlungssystems sind 159 Direktzahlungskulturen (Stand Juli 2026) definiert, welche im Rahmen der Strukturdatenerhebung von den Bewirtschaftenden in den kantonalen Agrarinformationssystemen (KAIS) eingetragen und an das agrarpolitische Informationssystem (AGIS) des Bundes übermittelt werden können.

Direktzahlungskulturen können für keine bis mehrere Beiträge berechtigt sein (Flächenkatalog und Beitragsberechtigung), grundsätzlich müssen sie für die Berechtigung zu Direktzahlungen aber jährlich an AGIS übermittelt werden. In AGIS stehen also alle aktuell gültigen und historisierten Direktzahlungskulturen und deren Beitragsberechtigungen (keine bis mehrere) für befugte Nutzende (Bund, Kantone) zur Verfügung. Momentan können diese Daten aber nicht in maschinenlesbarer Form vom AGIS-Webservice bezogen werden.

Die Direktzahlungskulturen kommen nicht nur im Rahmen der Strukturdatenerhebung zum Einsatz, sondern auch bei der gesamtschweizerischen räumlichen Erfassung von Nutzungsflächen. Die Kantone erfassen diese Geodaten gemäss dem minimalen Geodatenmodell 153.1 «Nutzungsflächen» und stellen die Daten via dem interkantonalen Portal geodienste.ch zur Verfügung (Landwirtschaftliche Kulturflächen). Die im Rahmen der Geodaten verwendeten Kulturkategorien sind als XML-File auf #link("https://models.geo.admin.ch") publiziert, wobei weitere (aggregierende) Kulturkategorien definiert wurden und die Attribute nicht zu 100% deckungsgleich sind.

Die Direktzahlungskulturen sind selbst in acht Kulturkategorien eingeteilt (#ref(<tbl-directpaymentcrops-categories>, supplement: [Tabelle])). Eine mehrheit dieser Kategorien wird explizit in der landwirtschaftlichen Begriffsverordnung (LBV) definiert.

#figure([
#table(
  columns: (6.45%, 19.35%, 32.26%, 41.94%),
  align: (left,left,left,left,),
  table.header([N], [Name], [Definition], [Beispiele],),
  table.hline(),
  [72], [Ackerfläche], [#link("https://www.fedlex.admin.ch/eli/cc/1999/13/de#art_18")[Art. 18 LBV]], [«Futterweizen gemäss Sortenliste swiss granum», «Winterraps zur Speiseölgewinnung», «Winterraps als nachwachsender Rohstoff»],
  [15], [Dauergrünfläche], [#link("https://www.fedlex.admin.ch/eli/cc/1999/13/de#art_19")[Art. 19 LBV]], [«Extensiv genutzte Wiesen (ohne Weiden)», «Übrige Grünfläche (Dauergrünfläche), beitragsberechtigt»],
  [27], [Dauerkulturen], [#link("https://www.fedlex.admin.ch/eli/cc/1999/13/de#art_22")[Art. 22 LBV]], [«Reben», «Obstanlagen (Äpfel)», «Reben (regionsspezifische Biodiversitätsförderfläche)»],
  [14], [Kulturen in ganzjährig geschütztem Anbau], [#link("https://www.fedlex.admin.ch/eli/cc/1999/13/de#art_14")[Art. 14 LBV]], [«Gemüsekulturen in Gewächshäusern mit festem Fundament», «Übrige Spezialkulturen in geschütztem Anbau ohne festes Fundament»],
  [6], [Weitere Flächen innerhalb der landwirtschaftlichen Nutzfläche], [], [«Streueflächen innerhalb der landwirtschaftlichen Nutzfläche», «Hecken-, Feld- und Ufergehölze (mit Pufferstreifen) (regionsspezifische Biodiversitätsförderfläche)»],
  [11], [Flächen ausserhalb der landwirtschaftlichen Nutzfläche], [], [«Wald», «Trockenmauern», «Hausgärten»],
  [5], [Flächen im Sömmerungsgebiet], [#link("https://www.fedlex.admin.ch/eli/cc/1999/13/de#art_24")[Art. 24 LBV]], [«Sömmerungsweiden», «Artenreiche Grün- und Streueflächen im Sömmerungsgebiet»],
  [9], [Andere Elemente], [], [«Hochstammfeldobstbäume», «Nussbäume», «Einheimische standortgerechte Einzelbäume und Alleen»],
)
], caption: figure.caption(
position: top, 
[
Kategorien der Direktzahlungskulturen mit Referenzen auf die landwirtschaftliche Begriffsverordnung (LBV), wo möglich.
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-directpaymentcrops-categories>


== Nährstoffbilanz
<sec-nutrient-balance>
Um umweltbelastende Nährstoffverluste zu verhindern und die Ertragsfähigkeit der Böden nachhaltig zu sichern, müssen Schweizer Landwirtschaftsbetriebe eine ausgeglichene Nährstoffbilanz ausweisen @grud2017. Das zentrale Berechnungsinstrument hierfür ist die Suisse-Bilanz, welche den Nährstoffanfall (etwa durch Hofdünger) und den Nährstoffbedarf auf Betriebsebene systematisch gegenüberstellt @suibi2025. Für diese Bilanzierung wurden spezifische Kulturen definiert, weil jede landwirtschaftliche Kultur einen anderen, normierten Nährstoffbedarf (z.B. für Stickstoff oder Phosphor) aufweist @grud2017. Die Zuweisung dieser Kulturen ist die Grundvoraussetzung, um eine Nährstoffbilanz für einen Betrieb berechnen zu können.

Um die Suisse-Bilanz zu berechnen, ist die «Wegleitung Suisse-Bilanz» entscheidend, welche von Agridea und dem Bundesamt für Landwirtschaft herausgegeben wird @suibi2025. In dem Dokument sind viele Referenztabellen enthalten, die entsprechend nach Kulturen aufgegliedert sind, abgeleitet von den detaillierteren Tabellen in #cite(<grud2017>, form: "prose").

Zur Standardisierung der Suisse-Bilanz-Berechnung stellt das Bundesamt für Landwirtschaft neu den Nährstoffbilanz-Berechnungsservice (NBBS) als RESTful API zur Verfügung. Über diese Schnittstelle lässt sich unter anderem ein Katalog der landwirtschaftlichen Kulturen abrufen.#footnote[Die «agronomischen Kulturkategorien» für den Nährstoffbilanzrechner sind beispielsweise über den Endpoint #link("https://rf-vp.agate.ch/digiflux/naebi/2-0/naebiservice-backend/agronomiccropcategories") abrufbar. Mittels der Slugs #NormalTok("cultivationcategories"); und #NormalTok("cultivationsubcategories"); lassen sich zudem die jeweiligen Übergruppen abfragen.] Der NBBS ordnet die Kulturen in einer strikten, dreistufigen Hierarchie (#ref(<tbl-nbbs-hierarchy>, supplement: [Tabelle])).

#figure([
#table(
  columns: (3.03%, 10.1%, 54.55%, 32.32%),
  align: (left,left,left,left,),
  table.header([N], [Name], [Beschreibung], [Beispiele],),
  table.hline(),
  [3], [Kultivierungskategorien (#NormalTok("cultivationcategories");)], [Oberste Hierarchieebene, dient nur der Strukturierung.], [Ackerkulturen, Grundfutterproduktion, Spezialkulturen],
  [8], [Kultivierungsunterkategorien (#NormalTok("cultivationsubcategories");)], [Mittlere Ebene, dient ebenfalls nur der Strukturierung.], [Getreide, Dauerkulturen, Hackfrüchte, Freilandgemüse, geschützte Kulturen, Grundfutter, übriger Ökoausgleich, diverse Kulturen],
  [314], [Agronomische Kulturkategorien (#NormalTok("agronomiccropcategories");)], [Unterste Ebene, welche die eigentlichen Kulturen beinhaltet. Hier sind die spezifischen agronomischen und regulatorische Eigenschaften hinterlegt.], [«Winterweizen», «Zuckerrüben», «Naturwiese extensiv», «Aubergine, Erdkultur (geschützter Anbau)», «Walnüsse ≥ 185 Bäume/ha»],
)
], caption: figure.caption(
position: top, 
[
Hierarchische Struktur der Kulturen im Nährstoffbilanz-Berechnungsservice. «N» ist die Anzahl Elemente je Klasse, Stand Juli 2026.
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-nbbs-hierarchy>


Während die beiden obersten Ebenen rein der Strukturierung und Gruppierung dienen, weisen die agronomischen Kulturkategorien auf der untersten Ebene spezifische agronomische und regulatorische Eigenschaften auf. Dazu gehören beispielsweise der Ertrag, die Zulässigkeit für bestimmte Direktzahlungsprogramme oder die Teilnahme an spezifischen Vorhaben wie dem «62a Nitrat-Projekt».

== Pflanzenschutz
<sec-plant-protection>
Das Pflanzenschutzmittelverzeichnis (PSMV) ist das offizielle Register des Bundes, das alle in der Schweiz zugelassenen Pflanzenschutzmittel auflistet und verbindlich regelt, für welche Kulturen und unter welchen Bedingungen diese rechtmässig eingesetzt werden dürfen. Es wird vom Bundesamt für Lebensmittelsicherheit und Veterinärwesen (BLV) gepflegt und umfasst 321 definierte Kulturen. Die Bezeichnungen dieser Kulturen liegen mehrsprachig auf Deutsch, Französisch und Italienisch sowie teilweise auf Englisch vor.

Anders als die streng monohierarchische Klassifikationen (wie in AGIS und im NBBS) sind die Kulturen im PSMV als Objekte in einer flexiblen Polyhierarchie modelliert. Dies bedeutet, dass ein Element mehr als ein Überelement aufweisen kann, welches wiederum eigenen Überelementen untergeordnet ist.

Diese Struktur wurde ursprünglich von der #emph[European Plant Protection Organization] (EPPO) abgeleitet, anschliessend aber für die spezifischen Schweizer Anforderungen weiter modifiziert. Die Organisation in Übergruppen erlaubt eine äusserst flexible Modellierung: Gewisse Äste der Hierarchie sind flach, während andere sehr tief verschachtelt sein können. Eine Kultur kann dabei bis zu zwei direkte Übergruppen besitzen. So ist beispielsweise die #emph[Sommergerste] sowohl der Übergruppe «Gerste» als auch dem «Sommergetreide» untergeordnet.

Die Hierarchietiefe kann bis zu fünf Übergruppen umfassen, wie folgendes Beispiel aus dem Gemüsebau verdeutlicht:

+ #strong[Schnittsalat], gehört zu
+ #strong[Blattsalate (Asteraceae)], gehört zu
+ #strong[Lactuca-Salate], gehört zu
+ #strong[Salate (Asteraceae)], gehört zu
+ #strong[Korbblütler (Asteraceae)], gehört zu
+ #strong[Gemüsebau allg.]

Die präzise Abbildung dieser Hierarchie ist fachlich von grosser Bedeutung, da die Zulassungslogik direkt in die Struktur des PSMV eingebaut ist. Wenn eine Pflanzenschutzmittel-Anwendung für eine übergeordnete Kulturgruppe bewilligt ist, gilt diese Bewilligung automatisch auch für sämtliche untergeordneten Kulturen.

Ein Beispiel hierfür: Das Herbizid #link("https://www.psm.admin.ch/de/produkte/7430")[«Ariane C»] ist gegen ein- und mehrjährige Dicotyledonen in Getreiden einsetzbar. Damit ist es bei allen Kulturen anwendbar, welche vom PSMV als Getreide klassifiziert werden. Mais gehört in diesem System aber explizit nicht zu den Getreiden -- in der Systematik des NBBS aber schon. Die korrekte Nachbildung dieser Polyhierarchie ist in den Daten folglich essenziell, um Zulassungen maschinell korrekt zu verarbeiten.

= Datenmodell
<datenmodell>
== Nutzung von Semantic-Web-Technologien
<nutzung-von-semantic-web-technologien>
Im Gegensatz zum Pflanzenschutzmittelverzeichnis wird beim Nährstoffbilanzrechner Mais als Getreide gezählt -- es existieren also verschiedene Definitionen von Getreide. Um diese eindeutig kennzeichnen zu können, setzen wir auf Linked Data. Für weiterführende Informationen zur Publikation, Nutzung und den Kernprozessen von vernetzten Daten verweisen wir auf #cite(<eCH-0205:1.0.0>, form: "prose").

Das konsolidierte Datenmodell wird durch eine RDFS-Ontologie abgebildet und mittels SHACL-Shapes validiert @rdf@owl2@shacl.

#figure([
#box(image("../assets/img/uml.png"))
], caption: figure.caption(
position: bottom, 
[
UML-Diagramm des Datenmodells.
]), 
kind: "quarto-float-fig", 
supplement: "Abbildung", 
)


TBC.

= Klassen
<klassen>
== Direktzahlungskultur
<sec-direktzahlungskultur>
Beschreibt eine Liste der «Kulturen», die gemäss Direktzahlungsverordnung im Bereich Landwirtschaft relevant sind. Diese «Kulturen» werden für den Direktzahlungsvollzug verwendet. Sie entsprechen den Hauptkulturen.

#strong[Zielklasse:] #NormalTok(":DirectPaymentCrop");

#figure([
#table(
  columns: (25%, 25%, 25%, 25%),
  align: (left,left,left,right,),
  table.header([Beschreibung], [Pfad], [Typ], [Kardinalität],),
  table.hline(),
  [#strong[Identifikator]: Der LNF-Code, auch Kulturcode genannt, ist der allgemein gebräuchliche Identifikator für Direktzahlungskulturen in der Schweiz.], [#NormalTok("schema:identifier");], [#NormalTok("xsd:string"); oder #NormalTok("sh:Literal");], [1..1],
  [#strong[Bezeichnung]], [#NormalTok("schema:name");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [1..\*],
  [#strong[Kulturgruppe]], [#NormalTok(":cultivationGroup");], [#link(<sec-nutzungstyp>)[:CultivationType] oder #NormalTok("sh:IRI");], [0..1],
  [#strong[Gültig von]: Ab welchem Jahr wurde diese Direktzahlungskultur offiziell verwendet?], [#NormalTok("schema:validFrom");], [#NormalTok("xsd:integer"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[Gültig bis]: Bis in welchem Jahr wurde diese Direktzahlungskultur offiziell verwendet?], [#NormalTok("schema:validTo");], [], [0..1],
  [#strong[Kultivierungstyp]], [#NormalTok(":cultivationType");], [#link(<sec-nutzungstyp>)[:CultivationType]], [0..1],
)
], caption: figure.caption(
position: top, 
[
Direktzahlungskultur Eigenschaften
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-direktzahlungskultur>


== Nutzungstyp
<sec-nutzungstyp>
#strong[Zielklasse:] #NormalTok(":CultivationType");

#figure([
#table(
  columns: (25%, 25%, 25%, 25%),
  align: (left,left,left,right,),
  table.header([Beschreibung], [Pfad], [Typ], [Kardinalität],),
  table.hline(),
  [#strong[Name]], [#NormalTok("schema:name");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [1..\*],
  [], [#NormalTok("schema:alternateName");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [0..\*],
  [#strong[Beschreibung]], [#NormalTok("schema:description");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [0..\*],
  [#strong[Bild]], [#NormalTok("schema:image");], [#NormalTok("sh:IRI");], [0..\*],
  [], [#NormalTok("rdfs:subClassOf");], [#NormalTok("sh:IRI");], [0..\*],
  [], [#NormalTok("owl:intersectionOf");], [], [0..\*],
  [], [#NormalTok("owl:unionOf");], [], [0..\*],
  [], [#NormalTok("owl:disjointWith");], [#link(<sec-nutzungstyp>)[:CultivationType] oder #NormalTok("sh:IRI");], [0..\*],
  [#strong[Botanische Pflanze]], [#NormalTok(":botanicalPlant");], [#NormalTok("sh:IRI");], [0..1],
  [#strong[Anbauintensität]], [#NormalTok(":managementIntensity");], [#NormalTok("sh:IRI");], [0..1],
)
], caption: figure.caption(
position: top, 
[
Nutzungstyp Eigenschaften
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-nutzungstyp>


== Nutzungstyp
<sec-nutzungstyp>
#strong[Zielklasse:] #NormalTok(":DeprecatedCultivationType");

#figure([
#table(
  columns: (25%, 25%, 25%, 25%),
  align: (left,left,left,right,),
  table.header([Beschreibung], [Pfad], [Typ], [Kardinalität],),
  table.hline(),
  [#strong[Name]], [#NormalTok("schema:name");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [1..\*],
  [], [#NormalTok("schema:alternateName");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [0..\*],
  [#strong[Beschreibung]], [#NormalTok("schema:description");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [0..\*],
  [#strong[Bild]], [#NormalTok("schema:image");], [#NormalTok("sh:IRI");], [0..\*],
  [], [#NormalTok("rdfs:subClassOf");], [#NormalTok("sh:IRI");], [0..\*],
  [], [#NormalTok("owl:intersectionOf");], [], [0..\*],
  [], [#NormalTok("owl:unionOf");], [], [0..\*],
  [], [#NormalTok("owl:disjointWith");], [#link(<sec-nutzungstyp>)[:CultivationType] oder #NormalTok("sh:IRI");], [0..\*],
  [#strong[Botanische Pflanze]], [#NormalTok(":botanicalPlant");], [#NormalTok("sh:IRI");], [0..1],
  [#strong[Anbauintensität]], [#NormalTok(":managementIntensity");], [#NormalTok("sh:IRI");], [0..1],
)
], caption: figure.caption(
position: top, 
[
Nutzungstyp Eigenschaften
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-nutzungstyp>


== shape:NutrientBalanceCrop
<sec-shape-nutrientbalancecrop>
#strong[Zielklasse:] #NormalTok(":NutrientBalanceCrop");

#figure([
#table(
  columns: (25%, 25%, 25%, 25%),
  align: (left,left,left,right,),
  table.header([Beschreibung], [Pfad], [Typ], [Kardinalität],),
  table.hline(),
  [#strong[Identifikator]], [#NormalTok("schema:identifier");], [#NormalTok("xsd:string"); oder #NormalTok("sh:Literal");], [1..1],
  [#strong[Bezeichnung]], [#NormalTok("schema:name");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [1..1],
  [#strong[Kulturkategorie]], [#NormalTok(":cultivationCategory");], [#link(<sec-nutzungstyp>)[:CultivationType] oder #NormalTok("sh:IRI");], [1..1],
  [#strong[Kultur-Unterkategorie]], [#NormalTok(":cultivationSubCategory");], [#link(<sec-nutzungstyp>)[:CultivationType] oder #NormalTok("sh:IRI");], [1..1],
  [#strong[N]: Stickstoff, kg/ha], [#NormalTok(":N2");], [#NormalTok("xsd:decimal"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[P₂O₅]: Phosphor, kg/dt], [#NormalTok(":P2O5");], [#NormalTok("xsd:decimal"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[K₂O]: Kalium, kg/dt], [#NormalTok(":K2O");], [#NormalTok("xsd:decimal"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[Mg]: Magnesium, kg/dt], [#NormalTok(":Mg");], [#NormalTok("xsd:decimal"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[Kultivierungstyp]], [#NormalTok(":cultivationType");], [#link(<sec-nutzungstyp>)[:CultivationType]], [0..1],
)
], caption: figure.caption(
position: top, 
[
shape:NutrientBalanceCrop Eigenschaften
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-shape-nutrientbalancecrop>


== shape:PlantProtectionCrop
<sec-shape-plantprotectioncrop>
#strong[Zielklasse:] #NormalTok(":PlantProtectionCrop");

#figure([
#table(
  columns: (25%, 25%, 25%, 25%),
  align: (left,left,left,right,),
  table.header([Beschreibung], [Pfad], [Typ], [Kardinalität],),
  table.hline(),
  [#strong[Identifikator]], [#NormalTok("schema:identifier");], [#NormalTok("xsd:string"); oder #NormalTok("sh:Literal");], [1..1],
  [#strong[Name]: Der in Infofito eingetragene Name dieser Kultur], [#NormalTok("schema:name");], [#NormalTok("sh:Literal");], [2..4],
  [#strong[Version]], [#NormalTok("schema:version");], [#NormalTok("xsd:integer"); oder #NormalTok("sh:Literal");], [1..1],
  [#strong[Überkultur]], [#NormalTok("schema:isPartOf");], [#link(<sec-shape-plantprotectioncrop>)[:PlantProtectionCrop] oder #NormalTok("sh:IRI");], [0..2],
  [#strong[Unterkultur]], [#NormalTok("schema:hasPart");], [#link(<sec-shape-plantprotectioncrop>)[:PlantProtectionCrop] oder #NormalTok("sh:IRI");], [0..\*],
  [#strong[Kultivierungstyp]], [#NormalTok(":cultivationType");], [#link(<sec-nutzungstyp>)[:CultivationType]], [0..1],
)
], caption: figure.caption(
position: top, 
[
shape:PlantProtectionCrop Eigenschaften
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-shape-plantprotectioncrop>


= Nutzung der Daten
<nutzung-der-daten>
- Sämtliche hier beschriebenen Daten können auf LINDAS bezogen werden.
- Knappe Anleitung zum Beziehen der Daten.

= Sicherheitsaspekte
<sicherheitsaspekte>
Informationen zu den ausdrücklich massgeblichen rechtlichen Grundlagen oder ein Hinweis darauf, dass bei der Umsetzung die entsprechenden rechtlichen Grundlagen zu beachten sind.

= Haftungsausschluss
<haftungsausschluss>
eCH-Standards, die der Verein eCH dem Anwender kostenlos zur Verfügung stellt oder die auf eCH verweisen, haben nur den Status von Empfehlungen. Der Verein eCH haftet in keinem Fall für Entscheidungen oder Massnahmen, die der Anwender auf der Grundlage dieser Dokumente trifft bzw. ergreift. Der Anwender ist dafür verantwortlich, die Dokumente vor ihrer Verwendung selbst zu überprüfen und gegebenenfalls fachlichen Rat einzuholen. eCH-Standards können und sollen die technische, organisatorische oder rechtliche Beratung im Einzelfall nicht ersetzen.

Dokumente, Verfahren, Methoden, Produkte und Standards, auf die in eCH-Standards verwiesen wird, sind möglicherweise durch Marken-, Urheber- oder Patentrechte geschützt. Es liegt in der ausschliesslichen Verantwortung des Anwenders, die erforderlichen Lizenzen von den berechtigten Personen und/oder Organisationen einzuholen.

Obwohl der Verein eCH bei der Erstellung der eCH-Standards mit angemessener Sorgfalt vorgegangen ist, kann er keine Gewährleistung oder Garantie dafür übernehmen, dass die bereitgestellten Informationen und Dokumente aktuell, vollständig, richtig oder fehlerfrei sind. eCH behält sich das Recht vor, die Inhalte der eCH-Standards jederzeit und ohne vorherige Ankündigung zu ändern.

Jede Haftung für Schäden, die durch die Nutzung der eCH-Standards durch den Anwender entstehen, wird im gesetzlich zulässigen Rahmen ausgeschlossen.

= Urheberrechte
<urheberrechte>
Personen, die eCH-Standards erarbeiten, bleiben Inhaber ihrer geistigen Eigentumsrechte. Diese Personen verpflichten sich jedoch, ihre geistigen Eigentumsrechte oder andere Rechte an geistigen Eigentumsrechten Dritter, soweit möglich, den jeweiligen Fachgruppen und dem Verein eCH kostenlos und zur uneingeschränkten Nutzung und Weiterentwicklung im Rahmen des Vereinszwecks zur Verfügung zu stellen.

Die von den Fachgruppen erarbeiteten Standards dürfen unter Nennung des jeweiligen Autors von eCH kostenlos und in uneingeschränktem Umfang genutzt, verbreitet und weiterentwickelt werden.

eCH-Standards sind vollständig dokumentiert und frei von lizenz- und/oder patentrechtlichen Einschränkungen. Die dazugehörige Dokumentation kann kostenlos angefordert werden. Diese Bestimmungen gelten jedoch nur für die von eCH erarbeiteten Standards, nicht aber für Standards oder Produkte Dritter, die auf eCH-Standards verweisen. Die Standards enthalten die entsprechenden Hinweise auf Rechte Dritter.

= Anhang A - Referenzen
<anhang-a---referenzen>
#block[
] <refs>
= Anhang B - Mitwirkung und Prüfung
<anhang-b---mitwirkung-und-prüfung>
#figure([
#table(
  columns: 2,
  align: (left,left,),
  table.header([Name], [Organisation],),
  table.hline(),
  [Marc Beringer], [Bundesamt für Landwirtschaft],
  [Damian Oswald], [Bundesamt für Landwirtschaft],
  [Lea Stauber], [Bundesamt für Landwirtschaft],
  [Christian Wilda], [Bundesamt für Landwirtschaft],
)
], caption: figure.caption(
position: top, 
[
Autoren und Revision
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-authors>


= Anhang C - Abkürzungen und Glossar
<anhang-c---abkürzungen-und-glossar>
#figure([
#table(
  columns: 2,
  align: (left,left,),
  table.header([Abkürzung], [Beschreibung],),
  table.hline(),
  [AGIS], [Agrarpolitisches Informationssystem],
  [KAIS], [Kantonales Agrarinformationssystem],
  [NBBS], [Nährstoffbilanz-Berechnungsservice],
)
], caption: figure.caption(
position: top, 
[
Abkürzungsverzeichnis
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-abbreviations>


= Anhang D - Änderungen gegenüber der Vorversion
<anhang-d---änderungen-gegenüber-der-vorversion>
Das vorliegende Dokument ist ein Hilfsmittel zur harmonisierten, systemübergreifenden Nutzung von landwirtschaftlichen Kulturdaten in der Schweiz. Gegenüber der Version 1.1.0 (eCH-0265 Datenstandard Agrardaten -- Flächen und Kulturen) wurde das Dokument von einem unverbindlichen Standard zu einem Hilfsmittel umgewandelt. Gleichzeitig wurde der inhaltliche Fokus geschärft: Klassen rund um Geometrien/Flächen#footnote[Die Erhebung von landwirtschaftlichen Nutzflächen wird bereits mit dem minimale Geodatenmodell «Landwirtschaftliche Kulturflächen» (Identifikator 153) spezifiziert: #link("https://www.blw.admin.ch/de/landwirtschaftliche-kulturflaechen")], Sorten sowie Direktzahlungsprogrammen sind nicht mehr Teil dieses Dokuments#footnote[Eine spätere Wiederaufnahme von Sorten und Programmen bleibt vorbehalten.]. Neu enthalten sind dafür die Kulturen aus dem Pflanzenschutzmittelverzeichnis.

Eine vollständige Übersicht der Veränderungen wird auf GitHub geführt: #link("https://github.com/blw-ofag-ufag/eCH-0265/releases").

= Anhang E - Abbildungsverzeichnis
<anhang-e---abbildungsverzeichnis>
= Anhang F - Tabellenverzeichnis
<anhang-f---tabellenverzeichnis>



#bibliography(("../references.bib"))

