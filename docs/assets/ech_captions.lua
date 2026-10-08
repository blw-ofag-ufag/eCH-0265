-- Quarto filter for the website (runs after Quarto's own filters):
--
--   * sets the caption prefix of figures and tables in bold,
--     "**Tabelle 3:** Beschreibung" (the PDF does the same with a Typst
--     show rule in typst-template.typ);
--   * fills the placeholders of the shortcodes {{< ech figures >}} and
--     {{< ech tables >}} (see ech_shortcodes.lua) with linked lists of the
--     captions of all figures or tables of the document.

if not quarto.doc.is_format("html") then return {} end

-- Wraps the leading "Tabelle 3:" tokens of a caption in Strong.
local function embolden_prefix(inlines)
  for i = 1, math.min(#inlines, 4) do
    local inline = inlines[i]
    if inline.t == "Str" and inline.text:sub(-1) == ":" then
      local prefix = pandoc.Inlines({})
      for _ = 1, i do prefix:insert(inlines:remove(1)) end
      inlines:insert(1, pandoc.Strong(prefix))
      return true
    end
  end
  return false
end

-- Finds the caption of a rendered float: the block following Quarto's
-- "<figcaption ...>" raw block. Returns the kind ("fig" or "tbl") and the
-- caption inlines, or nil.
local function find_caption(blocks)
  for i, block in ipairs(blocks) do
    local nextblock = blocks[i + 1]
    if block.t == "RawBlock" and block.text:find("<figcaption", 1, true) and nextblock
      and (nextblock.t == "Plain" or nextblock.t == "Para") then
      local kind = block.text:find("quarto%-float%-tbl") and "tbl" or "fig"
      return kind, nextblock.content
    elseif block.t == "Div" then
      local kind, caption = find_caption(block.content)
      if kind then return kind, caption end
    end
  end
  return nil
end

local floats = { fig = {}, tbl = {} }

local function collect(div)
  if not div.classes:includes("quarto-float") or div.identifier == "" then return nil end
  local kind, caption = find_caption(div.content)
  if kind == nil then return nil end
  embolden_prefix(caption)
  if floats[kind] then
    table.insert(floats[kind], { id = div.identifier, caption = caption:clone() })
  end
  return div
end

-- Shortens a caption to its first sentence (prefix "Tabelle 3:" included):
-- everything up to the first Str that ends a sentence is kept.
local function first_sentence(inlines)
  local result = pandoc.Inlines({})
  for i, inline in ipairs(inlines) do
    result:insert(inline)
    -- the prefix is a Strong at the start; sentence ends are plain Str
    if i > 1 and inline.t == "Str" and inline.text:match("[.!?]$") then
      break
    end
  end
  return result
end

local function float_list(kind)
  local items = {}
  for _, float in ipairs(floats[kind]) do
    table.insert(items, pandoc.Plain({ pandoc.Link(first_sentence(float.caption), "#" .. float.id) }))
  end
  if #items == 0 then return pandoc.Blocks({}) end
  return pandoc.Blocks({ pandoc.BulletList(items) })
end

function Pandoc(doc)
  doc.blocks = doc.blocks:walk({ Div = collect })
  doc.blocks = doc.blocks:walk({
    Div = function(div)
      if div.classes:includes("ech-list-of-figures") then
        return pandoc.Div(float_list("fig"), pandoc.Attr("", { "ech-float-list" }))
      elseif div.classes:includes("ech-list-of-tables") then
        return pandoc.Div(float_list("tbl"), pandoc.Attr("", { "ech-float-list" }))
      end
    end,
  })
  return doc
end
