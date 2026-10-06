-- Quarto filter: translates the eCH metadata codes (docs/_ech.yml) into the
-- display values used by the Typst title page (typst-show.typ) and the HTML
-- title block (title-metadata.html).
--
-- Sets `ech-rows` (list of { label, values, bullets }) and `ech-display`
-- (number, version, status, tagline, page-prefix, page-infix, organisation,
-- summary) in the document metadata. For the website it also prefixes the
-- title with the eCH number and turns the abstract into an unnumbered,
-- unlisted first chapter.

local common = dofile(quarto.utils.resolve_path("ech-common.lua"))

function Pandoc(doc)
  local meta = doc.meta
  local display = common.display(meta, { include_name = not quarto.doc.is_format("html") })
  if display == nil then return doc end

  local rows = {}
  for _, row in ipairs(display.rows) do
    table.insert(rows, { label = row.label, values = row.values, bullets = row.bullets })
  end
  meta["ech-rows"] = rows
  -- The website shows "eCH-0000 – Name" as title, like the PDF.
  if quarto.doc.is_format("html") and display.number and meta.title then
    local title = pandoc.Inlines({})
    title:extend(display.number)
    title:extend(pandoc.Inlines(pandoc.Str(" – ")))
    title:extend(pandoc.utils.type(meta.title) == "Inlines" and meta.title or pandoc.Inlines(pandoc.Str(pandoc.utils.stringify(meta.title))))
    meta.title = title
  end
  if quarto.doc.is_format("html") and meta.abstract then
    local abstract = meta.abstract
    if pandoc.utils.type(abstract) == "Inlines" then abstract = pandoc.Blocks(pandoc.Para(abstract)) end
    local heading = pandoc.Header(1, display.summary, pandoc.Attr("sec-summary", { "unnumbered", "unlisted" }))
    doc.blocks = pandoc.Blocks({ heading }) .. abstract .. doc.blocks
    meta.abstract = nil
  end
  meta["ech-display"] = {
    number = display.number,
    version = display.version,
    status = display.status,
    tagline = display.tagline,
    ["page-prefix"] = display["page-prefix"],
    ["page-infix"] = display["page-infix"],
    organisation = display.organisation,
    summary = display.summary,
  }
  return doc
end
