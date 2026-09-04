#show heading.where(level: 1): it => {
  colbreak(weak: true)
  it
}
#show heading.where(level: 1): set text(size: 16pt, weight: "bold")
#show heading.where(level: 2): set text(size: 12pt, weight: "bold")
#show heading: set block(above: 1.8em, below: 1em)
#show outline: set text(size: 11pt)
#show outline: set par(spacing: 1.25em)
#show figure.caption: set text(size: 10pt)
#show table.cell: set text(size: 10pt)
#show table.cell: set par(justify: false)
#show footnote.entry: set text(size: 10pt)
#show link: set text(fill: rgb("#D00D28"))
#set table(fill: (col, row) => if calc.even(row) { rgb("f2f2f2") } else { white })
#show table.cell.where(y: 0): set text(weight: "bold")
#show table: it => block(
  stroke: (top: 1pt + black, bottom: 1pt + black),
  inset: (top: 0.5pt, bottom: 0.5pt),
  outset: 0pt,
  breakable: true,
  it
)
#set page(
  header: context [
    #grid(
      columns: (35%, 1fr),
      align(left + bottom)[#image("../assets/ech.svg", width: 100%)],
      align(right + bottom)[Page #counter(page).display() of #counter(page).final().first()]
    )
    #v(0.25em)
    #line(length: 100%, stroke: 0.5pt + black)
  ],
  footer: [
    #line(length: 100%, stroke: 0.5pt + black)
    #v(0.25em)
    #align(left)[Verein eCH]
  ]
)