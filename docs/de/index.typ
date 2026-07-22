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
  date: [22. Juli 2026],
  lang: "de",
  abstract: [Dieses Hilfsmittel beinhaltet ein Datenmodell zu landwirtschaftlichen Kulturen der Schweiz sowie dazugehörende Referenzobjekte, welche als Linked Data maschinenlesbar bezogen werden können. Damit soll der fachlich validierte Datenaustausch und die Mehrfachnutzung von Daten zwischen den Bereichen der Direktzahlungen, der Nährstoffbilanz sowie des Pflanzenschutzes ermöglicht werden.

],
  abstract-title: "Zusammenfassung",
  toc_title: [Inhaltsverzeichnis],
  toc_depth: 3,
  doc,
)

#heading(level: 1, numbering: none)[Hinweis]
<hinweis>
Im vorliegenden Dokument wird bei der Bezeichnung von Personen eine geschlechtsneutrale Formulierung verwendet. Basis bildet der Leitfaden der Bundeskanzlei. Je nach Situation kommen Paarformen (Bürgerinnen und Bürger), geschlechtsabstrakte Formen (versicherte Person), geschlechtsneutrale Formen (Versicherte) oder Umschreibungen ohne Personenbezug zum Einsatz. Das generische Maskulin (Bürger) ist nicht zulässig. Vollformen werden in fortlaufenden Texten verwendet, also in Texten, die aus ausformulierten Sätzen bestehen. In verknappten Textpassagen, namentlich in Tabellen, können Kurzformen verwendet werden. Dabei wird die Kurzform mit Schrägstrich, aber ohne Auslassungsstrich verwendet (Referent/in). Genderstern und ähnliche Schreibweisen werden nicht verwendet.

= Einleitung
<einleitung>
== Status
<status>
TODO

== Geltungsbereich
<geltungsbereich>
TODO

= Einführung
<einführung>
Das vorliegende Dokument ist ein Hilfsmittel zur harmonisierten, systemübergreifenden Nutzung von landwirtschaftlichen Kulturdaten in der Schweiz. Gegenüber der Version 1.1.0 (eCH-0265 Datenstandard Agrardaten -- Flächen und Kulturen) wurde das Dokument von einem unverbindlichen Standard zu einem Hilfsmittel umgewandelt. Gleichzeitig wurde der inhaltliche Fokus geschärft: Die Übertragung von Geometrien/Flächen#footnote[Die Erhebung von landwirtschaftlichen Nutzflächen wird mit dem \[…\] spezifiziert.], Sorten sowie Direktzahlungsprogrammen ist nicht mehr Teil dieses Dokuments#footnote[Eine spätere Wiederaufnahme von Sorten und Programmen bleibt vorbehalten.]. Neu enthalten sind dafür die Kulturen aus dem Pflanzenschutzmittelverzeichnis.

Im Zentrum der Version 2.0.0 stehen die Repräsentationen von Kultur-Kategorien aus drei verschiedenen Bereichen (Direktzahlungen, Nährstoffbilanz und Pflanzenschutz) im Zentrum. Das Hilfsmittel soll dabei dienen, die Kulturen aus einem Bereich fachlich korrekt auf diejenigen in einem anderen Bereich übersetzen zu können.

Dies wird über eine zentrale Ontologie erreicht, mit welcher die landwirtschaftlichen Kulturen aus den verschiedenen Bereichen verbunden sind. Damit schafft dieses Hilfsmittel eine zentrale Datenquelle, welche in verschiedenen maschinenlesbaren Formaten über die LINDAS-Plattform in Form von Linked Data bezogen werden kann.

= Datenmodell
<datenmodell>
== shape:CultivationType
<sec-shape-cultivationtype>
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
  [], [#NormalTok("owl:disjointWith");], [#link(<sec-shape-cultivationtype>)[:CultivationType] oder #NormalTok("sh:IRI");], [0..\*],
  [], [#NormalTok(":botanicalPlant");], [#NormalTok("sh:IRI");], [0..1],
  [#strong[Anbauintensität]], [#NormalTok(":managementIntensity");], [#NormalTok("sh:IRI");], [0..1],
)
], caption: figure.caption(
position: top, 
[
shape:CultivationType Eigenschaften
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-shape-cultivationtype>


== shape:CultivationType
<sec-shape-cultivationtype>
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
  [], [#NormalTok("owl:disjointWith");], [#link(<sec-shape-cultivationtype>)[:CultivationType] oder #NormalTok("sh:IRI");], [0..\*],
  [], [#NormalTok(":botanicalPlant");], [#NormalTok("sh:IRI");], [0..1],
  [#strong[Anbauintensität]], [#NormalTok(":managementIntensity");], [#NormalTok("sh:IRI");], [0..1],
)
], caption: figure.caption(
position: top, 
[
shape:CultivationType Eigenschaften
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-shape-cultivationtype>


== shape:DirectPaymentCrop
<sec-shape-directpaymentcrop>
#strong[Zielklasse:] #NormalTok(":DirectPaymentCrop");

#figure([
#table(
  columns: (25%, 25%, 25%, 25%),
  align: (left,left,left,right,),
  table.header([Beschreibung], [Pfad], [Typ], [Kardinalität],),
  table.hline(),
  [#strong[Identifikator]: Der LNF-Code, auch Kulturcode genannt, ist der allgemein gebräuchliche Identifikator für Direktzahlungskulturen in der Schweiz.], [#NormalTok("schema:identifier");], [#NormalTok("xsd:string"); oder #NormalTok("sh:Literal");], [1..1],
  [#strong[Bezeichnung]], [#NormalTok("schema:name");], [#NormalTok("rdf:langString"); oder #NormalTok("sh:Literal");], [1..\*],
  [#strong[Kulturgruppe]], [#NormalTok(":cultivationGroup");], [#link(<sec-shape-cultivationtype>)[:CultivationType] oder #NormalTok("sh:IRI");], [0..1],
  [#strong[Gültig von]: Ab welchem Jahr wurde diese Direktzahlungskultur offiziell verwendet?], [#NormalTok("schema:validFrom");], [#NormalTok("xsd:integer"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[Gültig bis]: Bis in welchem Jahr wurde diese Direktzahlungskultur offiziell verwendet?], [#NormalTok("schema:validTo");], [], [0..1],
  [#strong[Kultivierungstyp]], [#NormalTok(":cultivationType");], [#link(<sec-shape-cultivationtype>)[:CultivationType]], [0..1],
)
], caption: figure.caption(
position: top, 
[
shape:DirectPaymentCrop Eigenschaften
]), 
kind: "quarto-float-tbl", 
supplement: "Tabelle", 
)
<tbl-shape-directpaymentcrop>


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
  [#strong[Kulturkategorie]], [#NormalTok(":cultivationCategory");], [#link(<sec-shape-cultivationtype>)[:CultivationType] oder #NormalTok("sh:IRI");], [1..1],
  [#strong[Kultur-Unterkategorie]], [#NormalTok(":cultivationSubCategory");], [#link(<sec-shape-cultivationtype>)[:CultivationType] oder #NormalTok("sh:IRI");], [1..1],
  [#strong[N]: Stickstoff, kg/ha], [#NormalTok(":N2");], [#NormalTok("xsd:decimal"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[P₂O₅]: Phosphor, kg/dt], [#NormalTok(":P2O5");], [#NormalTok("xsd:decimal"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[K₂O]: Kalium, kg/dt], [#NormalTok(":K2O");], [#NormalTok("xsd:decimal"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[Mg]: Magnesium, kg/dt], [#NormalTok(":Mg");], [#NormalTok("xsd:decimal"); oder #NormalTok("sh:Literal");], [0..1],
  [#strong[Kultivierungstyp]], [#NormalTok(":cultivationType");], [#link(<sec-shape-cultivationtype>)[:CultivationType]], [0..1],
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
  [#strong[Kultivierungstyp]], [#NormalTok(":cultivationType");], [#link(<sec-shape-cultivationtype>)[:CultivationType]], [0..1],
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
= Anhang B - Mitwirkung & Prüfung
<anhang-b---mitwirkung-prüfung>
= Anhang C - Abkürzungen und Glossar
<anhang-c---abkürzungen-und-glossar>
= Anhang D - Änderungen gegenüber der Vorversion
<anhang-d---änderungen-gegenüber-der-vorversion>
= Anhang E - Abbildungsverzeichnis
<anhang-e---abbildungsverzeichnis>
= Anhang F - Tabellenverzeichnis
<anhang-f---tabellenverzeichnis>



#bibliography(("../references.bib"))

