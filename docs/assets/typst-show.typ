#show: doc => ech-document(
$if(title)$
  title: [$title$],
$endif$
$if(date)$
  date: [$date$],
$endif$
$if(abstract)$
  abstract: [$abstract$],
$endif$
$if(lang)$
  lang: "$lang$",
$endif$
$if(region)$
  region: "$region$",
$endif$
$if(mainfont)$
  font: ("$mainfont$",),
$endif$
$if(monofont)$
  codefont: ("$monofont$",),
$endif$
$if(fontsize)$
  fontsize: $fontsize$,
$endif$
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
$if(toc)$
  toc: $toc$,
$endif$
$if(toc-title)$
  toc_title: [$toc-title$],
$endif$
  toc_depth: $toc-depth$,
$if(ech-display)$
  ech: (
$if(ech-display.number)$
    number: [$ech-display.number$],
$endif$
$if(ech-display.version)$
    version: [$ech-display.version$],
$endif$
$if(ech-display.status)$
    status: [$ech-display.status$],
$endif$
    tagline: [$ech-display.tagline$],
    page-prefix: [$ech-display.page-prefix$],
    page-infix: [$ech-display.page-infix$],
    organisation: [$ech-display.organisation$],
    summary: [$ech-display.summary$],
$if(ech-display.unpublished)$
    unpublished: true,
$endif$
    rows: (
$for(ech-rows)$
      (
        label: [$it.label$],
        bullets: $if(it.bullets)$true$else$false$endif$,
        values: ($for(it.values)$[$it$], $endfor$),
      ),
$endfor$
    ),
  ),
$endif$
  doc,
)
