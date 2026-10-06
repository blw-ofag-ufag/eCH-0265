// eCH document template for Quarto's Typst (PDF) output.
//
// The layout follows the eCH Word template (eCH-0003 V11.1.0, attachment
// "XXXX_d_DRA_JJJJ-MM-TT_eCH-0XXX_Vx.x.x_Titel.docx") and the published eCH
// standards: a title page with the metadata table and the summary, the table
// of contents on a new page, a header with the eCH logo, the tagline and the
// page count, and a two-line footer with the document identification.
//
// All eCH texts arrive translated from the Lua filter docs/assets/ech-metadata.lua
// via typst-show.typ, in the `ech` dictionary:
//
//   number, version, status          Inlines for the footer
//   tagline, page-prefix, page-infix, organisation, summary
//   rows: ((label, values, bullets), ...)   the metadata table

// Renders the values of a metadata row: "---" when missing, a bullet list or
// one value per line when several.
#let ech-values(values, bullets) = {
  if values.len() == 0 { return "---" }
  if values.len() == 1 { return values.first() }
  if bullets { return list(..values) }
  values.join(linebreak())
}

#let ech-document(
  title: none,
  date: none,
  abstract: none,
  lang: "de",
  region: none,
  font: ("Nimbus Sans",),
  codefont: ("DejaVu Sans Mono",),
  fontsize: 11pt,
  sectionnumbering: "1.1.1",
  toc: true,
  toc_title: none,
  toc_depth: 3,
  ech: none,
  doc,
) = {
  let ech = if ech == none { (:) } else { ech }
  let meta(key, default: none) = ech.at(key, default: default)

  let number = meta("number")
  let full-title = if number == none { title } else [#number – #title]
  let identification = [
    #full-title / #meta("version", default: "---") / *#meta("status", default: "---")* / #if date == none { "---" } else { date }
  ]

  // Document ----------------------------------------------------------------

  set document(title: full-title)
  set text(font: font, size: fontsize, lang: lang, hyphenate: true)
  set text(region: region) if region != none
  set par(justify: true, leading: 0.65em, spacing: 1.2em)
  set heading(numbering: sectionnumbering)

  // Page: A4 with 2 cm left and 1.5 cm right margin; header and footer are
  // separated from the body by a thin rule.
  // Documents not yet published (status before "approved"): a red
  // "PRE-RELEASE" ribbon across the top right corner of the title page.
  let unpublished = meta("unpublished", default: false)
  set page(foreground: context if unpublished and counter(page).get().first() == 1 {
    place(top + right, dx: 4.6cm, dy: 1.85cm, rotate(45deg, origin: center, block(
      width: 14cm, fill: rgb("#D00D28"), inset: (y: 10pt),
      align(center, text(fill: white, weight: "bold", size: 12pt)[PRE-RELEASE]),
    )))
  })

  set page(
    margin: (top: 3.1cm, bottom: 3.2cm, left: 2cm, right: 1.5cm),
    header-ascent: 0.5cm,
    footer-descent: 0.5cm,
    header: context {
      set text(size: 11pt)
      grid(
        columns: (auto, 1fr, auto),
        column-gutter: 0.45cm,
        align: bottom,
        image("../assets/ech.svg", height: 1.14cm),
        meta("tagline", default: "E-Government Standards"),
        // the ribbon of unpublished documents covers this corner on the title page
        if unpublished and counter(page).get().first() == 1 { [] } else {
          [#meta("page-prefix", default: "Page") #counter(page).display() #meta("page-infix", default: "of") #counter(page).final().first()]
        },
      )
      v(0.3cm)
      line(length: 100%, stroke: 0.5pt)
    },
    footer: {
      set text(size: 10pt)
      set par(leading: 0.5em, justify: false)
      show link: underline
      line(length: 100%, stroke: 0.5pt)
      v(0.2cm)
      grid(
        columns: (1fr, auto),
        row-gutter: 0.6em,
        meta("organisation", default: "Verein eCH"),
        [#link("https://www.ech.ch", "www.ech.ch") / #link("mailto:info@ech.ch", "info@ech.ch")],
        grid.cell(colspan: 2, identification),
      )
    },
  )

  // Headings: numbered chapters and the first appendix start on a new page,
  // the remaining appendices and other unnumbered chapters do not.
  let previous-numbered = state("ech-previous-numbered", false)
  show heading.where(level: 1): it => {
    context if it.numbering != none or previous-numbered.get() { pagebreak(weak: true) }
    previous-numbered.update(it.numbering != none)
    it
  }
  show heading.where(level: 1): set text(size: 16pt)
  show heading.where(level: 2): set text(size: 12pt)
  show heading.where(level: 3): set text(size: 11pt)
  show heading.where(level: 4): set text(size: 11pt, weight: "regular", style: "italic")
  show heading: set block(above: 1.8em, below: 1em)
  show heading.where(level: 1): set block(below: 1.4em)

  // Table of contents: levels 1 and 2 bold, numbers in a fixed column,
  // unnumbered chapters (appendices) across the full width.
  show outline.entry: it => {
    show link: set text(fill: black)
    if it.element.func() == figure {
      // Lists of figures and tables (appendices): "Abbildung 1: caption ... 5".
      block(width: 100%, link(it.element.location(), [*#it.prefix():* #it.inner()]))
    } else {
      set text(size: if it.level == 1 { 12pt } else { 11pt })
      set text(weight: "bold") if it.level <= 2
      let cells = if it.prefix() == none {
        (grid.cell(colspan: 2, it.inner()),)
      } else {
        (it.prefix(), it.inner())
      }
      link(it.element.location(), grid(columns: (1.5cm, 1fr), ..cells))
    }
  }
  show outline.entry.where(level: 1): set block(above: 1.2em)
  show outline: set par(spacing: 0.7em)

  // Marked text in a soft yellow (like the website); small caps synthesized
  // from capitals, since Nimbus Sans has no small-caps glyphs.
  show highlight: set highlight(fill: rgb("fff3cd"))
  show smallcaps: it => text(size: 0.8em, upper(it.body))

  // Links, code, figures, footnotes.
  show link: set text(fill: rgb("#D00D28"))
  show ref: set text(fill: rgb("#D00D28"))   // cross-references to equations etc.
  show link: it => {
    show raw: underline.with(stroke: 0.6pt, offset: 0.9pt)
    it
  }
  // Inline code: text colour on a rounded grey background that is darker
  // than the table stripes. A code span is never split: if it does not fit
  // on the current line, it moves to the next one as a whole. Real spaces
  // in the code become figure spaces so they keep their width.
  show raw.where(block: false): it => {
    set text(fill: black)
    // The horizontal padding is part of the box (`inset`), so neighbouring
    // text is pushed away; the vertical padding is painted only (`outset`)
    // and does not change the line height.
    box(
      fill: rgb("dcdcdc"),
      radius: 2.5pt,
      inset: (x: 2.5pt, y: 0pt),
      outset: (y: 1.2pt),
      text(font: codefont, it.text.replace(" ", "\u{2007}")),
    )
  }

  // Definition lists (e.g. the fact sheets of the data model) as key-value
  // rows, like the metadata table of the title page.
  // (Items must be styled individually: Quarto's own rule on terms.item
  // means that no `terms` element ever exists at realization time.)
  show terms.item: it => {
    set par(justify: false)
    block(
      above: 0.55em,
      below: 0.55em,
      grid(
        columns: (3.4cm, 1fr),
        column-gutter: 0.5em,
        text(hyphenate: false, strong(it.term)),
        it.description,
      ),
    )
  }

  // Code blocks (Quarto's Skylighting output) consist of inline raw tokens;
  // render them as plain monospaced text so the inline-code styling above
  // does not apply to them.
  show block.where(fill: rgb("#f1f3f5")): it => {
    show raw.where(block: false): token => if token.text == "\n" {
      linebreak()
    } else {
      text(font: codefont, token.text.replace(" ", "\u{2007}"))
    }
    it
  }

  show figure.caption: set text(size: 10pt)
  show figure.caption: it => context [
    *#it.supplement #it.counter.display(it.numbering):* #it.body
  ]
  show footnote.entry: set text(size: 10pt)

  // Tables: bold header row, zebra stripes, rules above and below. Quarto
  // wraps tables in figures, which must be made breakable for long tables.
  show figure.where(kind: "quarto-float-tbl"): set block(breakable: true)
  // Rows stay together: a page break never splits a cell.
  show table.cell: it => block(breakable: false, width: 100%, it)
  show table.cell: set text(size: 10pt)
  show table.cell: set par(justify: false)
  show table.cell.where(y: 0): set text(weight: "bold", hyphenate: false)
  set table(
    fill: (col, row) => if calc.even(row) { rgb("f2f2f2") } else { white },
    stroke: none,
  )
  show table: it => block(
    stroke: (top: 1pt + black, bottom: 1pt + black),
    inset: (top: 0.5pt, bottom: 0.5pt),
    outset: 0pt,
    breakable: true,
    it,
  )

  // Title page ----------------------------------------------------------------

  {
    set par(justify: false, leading: 0.45em)
    set text(size: 18pt, weight: "bold")
    block(below: 1cm, full-title)
  }

  let rows = meta("rows", default: ())
  if rows.len() > 0 {
    set par(justify: false)
    show link: underline
    grid(
      columns: (4.6cm, 1fr),
      stroke: 0.5pt,
      inset: (x: 4pt, y: 7pt),
      align: (x, y) => if x == 0 { horizon } else { top },
      ..rows.map(row => (strong(row.label), ech-values(row.values, row.bullets))).flatten(),
    )
  }

  if abstract != none {
    block(above: 1.1cm, below: 0.6cm, text(size: 16pt, weight: "bold", meta("summary", default: "Summary")))
    abstract
  }

  pagebreak()

  // Table of contents and body --------------------------------------------------

  if toc {
    outline(title: toc_title, depth: toc_depth, indent: 0pt)
  }

  doc
}

#set table(
  inset: 6pt,
  stroke: none
)
