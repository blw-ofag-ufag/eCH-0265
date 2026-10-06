-- Shared logic of the eCH metadata filter and shortcodes.
--
-- Reads the language-neutral codes under `ech` in the document metadata
-- (see docs/_ech.yml) and translates them with docs/assets/ech-vocabulary.yml
-- into the rows of the eCH title page and a few display strings.

local M = {}

local stringify = pandoc.utils.stringify

-- Converts a metadata value (string, number, Inlines, Blocks) into Inlines.
local function to_inlines(value)
  local kind = pandoc.utils.type(value)
  if kind == "Inlines" then
    return value
  elseif kind == "Blocks" then
    return pandoc.utils.blocks_to_inlines(value)
  elseif kind == "string" or kind == "number" then
    return pandoc.Inlines(pandoc.Str(tostring(value)))
  elseif kind == "List" and #value == 1 then
    return to_inlines(value[1])
  end
  error("eCH metadata: cannot render value of type " .. kind)
end

-- Converts a metadata value into a list of Inlines (one per entry).
local function to_list(value)
  if value == nil then return {} end
  if pandoc.utils.type(value) == "List" then
    local result = {}
    for _, item in ipairs(value) do table.insert(result, to_inlines(item)) end
    return result
  end
  return { to_inlines(value) }
end

local function concat(...)
  local result = pandoc.Inlines({})
  for _, part in ipairs({ ... }) do
    if type(part) == "string" then
      result:extend(pandoc.Inlines(pandoc.Str(part)))
    else
      result:extend(part)
    end
  end
  return result
end

-- Looks up `code` in the vocabulary table `group`; unknown codes are errors.
local function lookup(vocabulary, group, code)
  local entry = vocabulary[group] and vocabulary[group][code]
  if entry == nil then
    local allowed = {}
    for key, _ in pairs(vocabulary[group] or {}) do table.insert(allowed, key) end
    table.sort(allowed)
    error(string.format("eCH metadata: unknown %s '%s' (allowed: %s)",
      group, code, table.concat(allowed, ", ")))
  end
  return to_inlines(entry)
end

local vocabulary_cache = nil

-- Loads the vocabulary file next to this script.
function M.vocabulary(lang)
  if vocabulary_cache == nil then
    local path = quarto.utils.resolve_path("ech-vocabulary.yml")
    local file = assert(io.open(path, "r"), "eCH vocabulary not found: " .. path)
    local yaml = file:read("a")
    file:close()
    vocabulary_cache = pandoc.read("---\n" .. yaml .. "\n---\n", "markdown").meta
  end
  local entry = vocabulary_cache[lang]
  if entry == nil then
    error("eCH metadata: no vocabulary for language '" .. tostring(lang) .. "'")
  end
  return entry
end

-- Returns the translated eCH metadata of a document, or nil if it has none.
--
--   rows        ordered list of { key, label, values, bullets } for the title page
--   number, version, status, title    Inlines for header, footer and title
--   tagline, page-prefix, page-infix, organisation, summary   fixed PDF texts
--   status-text Inlines for the "Status" chapter
--
-- `options.include_name` controls whether the "Name" row is part of `rows`.
function M.display(meta, options)
  options = options or {}
  local ech = meta.ech
  if ech == nil then return nil end

  local lang = meta.lang and stringify(meta.lang) or "de"
  local voc = M.vocabulary(lang)
  local rows = {}

  -- Rows without values are rendered as "---" by the templates.
  local function add(key, values, bullets)
    table.insert(rows, {
      key = key,
      label = to_inlines(voc.labels[key]),
      -- an explicit MetaList: pandoc would turn an empty Lua table into `true`
      values = pandoc.MetaList(values or {}),
      bullets = bullets or false,
    })
  end

  local function code(key) return ech[key] and stringify(ech[key]) or nil end

  local number = ech.number and to_inlines(ech.number) or nil
  local version = ech.version and to_inlines(ech.version) or nil
  -- Documents whose status precedes "approved" are not published yet.
  local unpublished_statuses = { ["in-progress"] = true, draft = true, proposal = true }
  local unpublished = code("status") ~= nil and unpublished_statuses[code("status")] == true
  local status = code("status") and lookup(voc, "status", code("status")) or nil

  if options.include_name ~= false and meta.title then
    add("name", { to_inlines(meta.title) })
  end
  add("number", number and { number })
  add("category", code("category") and { lookup(voc, "category", code("category")) })
  add("maturity", code("maturity") and { lookup(voc, "maturity", code("maturity")) })
  add("version", version and { version })
  add("status", status and { status })
  add("decision-date", ech["decision-date"] and { to_inlines(ech["decision-date"]) })
  add("issue-date", meta.date and { to_inlines(meta.date) })

  local replaces = ech.replaces
  if replaces ~= nil then
    local change = replaces.change and lookup(voc, "change", stringify(replaces.change))
    if replaces.version == nil or (replaces.change and stringify(replaces.change) == "new") then
      add("replaces", { change or lookup(voc, "change", "new") })
    elseif change then
      add("replaces", { concat(to_inlines(replaces.version), " – ", change) })
    else
      add("replaces", { to_inlines(replaces.version) })
    end
  else
    add("replaces", nil)
  end

  local prerequisites = to_list(ech.prerequisites)
  add("prerequisites", prerequisites, #prerequisites > 1)
  local attachments = to_list(ech.attachments)
  add("attachments", attachments, #attachments > 1)

  if ech.languages ~= nil then
    -- Quarto rewrites metadata strings that match an existing path relative
    -- to the document (docs/de exists, so "de" becomes "../de"): keep the
    -- last path component only.
    local function language_code(value) return stringify(value):match("([^/]+)$") end
    local parts = {}
    local original = ech.languages.original and language_code(ech.languages.original)
    if original then
      table.insert(parts, concat(lookup(voc, "language", original), " (", to_inlines(voc.original), ")"))
    end
    for _, item in ipairs(ech.languages.translations or {}) do
      table.insert(parts, concat(lookup(voc, "language", language_code(item)), " (", to_inlines(voc.translation), ")"))
    end
    local languages = pandoc.Inlines({})
    for i, part in ipairs(parts) do
      if i > 1 then languages:extend(pandoc.Inlines(pandoc.Str(", "))) end
      languages:extend(part)
    end
    add("languages", { languages })
  else
    add("languages", nil)
  end

  add("group", ech.group and { concat(to_inlines(voc["group-prefix"]), " ", to_inlines(ech.group)) })
  add("publisher", to_list(ech.publisher or voc.publisher))

  local status_text = nil
  if status then
    local description = voc["status-description"][code("status")]
    status_text = concat(status, ": ", to_inlines(description))
  end

  return {
    rows = rows,
    number = number,
    version = version,
    unpublished = unpublished,
    status = status,
    ["status-text"] = status_text,
    tagline = to_inlines(voc.tagline),
    ["page-prefix"] = to_inlines(voc["page-prefix"]),
    ["page-infix"] = to_inlines(voc["page-infix"]),
    organisation = to_inlines(voc.organisation),
    summary = to_inlines(voc.summary),
  }
end

return M
