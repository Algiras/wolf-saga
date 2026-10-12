-- Quarto filter for the store e-book (format saga-store-epub).
--
--   * the licence chapter (copyright.qmd) moves to the front, right after the title page;
--   * an inline table of contents page follows it (the EPUB also carries the nav TOC);
--   * the web-only reading-order page is dropped;
--   * part titles become real top-level headings (Quarto leaves them buried in a wrapper
--     div, so the stock EPUB has no part pages), and the chapters inside a part become
--     level 2, giving the nav TOC a Part > Chapter tree (needs epub-chapter-level: 2);
--   * scene breaks (--- and * * *) become a centred "* * *" paragraph; the place/date line
--     under a chapter title becomes a centred block.

local stringify = pandoc.utils.stringify

local COPYRIGHT = { ["Licencija"] = true, ["License"] = true, ["Licence"] = true }
local DROP = { ["Skaitymo tvarka"] = true, ["Reading order"] = true }

local function is_part(b)
  return b.t == "Div" and b.classes:includes("quarto-book-part")
end

local function is_file_marker(b)
  return b.t == "RawBlock" and b.format == "html" and b.text:find("quarto-file-metadata", 1, true) ~= nil
end

local function is_unnumbered(h)
  return h.classes:includes("unnumbered") or h.classes:includes("unlisted")
end

local function is_break_para(b)
  return b.t == "Para" and stringify(b):gsub("%s", "") == "***"
end

local function scene_break()
  return pandoc.Div({ pandoc.Para({ pandoc.Str("*\u{a0}*\u{a0}*") }) }, pandoc.Attr("", { "scenebreak" }))
end

function Pandoc(doc)
  local meta = doc.meta
  local out, copyright = {}, {}
  local mode = nil
  local in_part = false

  for _, b in ipairs(doc.blocks) do
    local boundary = is_file_marker(b) or is_part(b) or (b.t == "Header" and b.level == 1)
    if boundary then mode = nil end

    if b.t == "Header" and b.level == 1 then
      local t = stringify(b.content)
      if COPYRIGHT[t] then mode = "copyright" elseif DROP[t] then mode = "drop" end
    end

    if mode == "copyright" then
      if b.t == "Header" then
        b.classes = pandoc.List({ "unnumbered", "unlisted", "copyright-page" })
        b.attributes["epub:type"] = "copyright-page"
      end
      if not is_file_marker(b) then copyright[#copyright + 1] = b end
    elseif mode ~= "drop" then
      if is_part(b) then
        for _, x in ipairs(b.content) do
          if x.t == "Header" then
            x.classes:insert("part")
            x.attributes["epub:type"] = "part"
            out[#out + 1] = x
          end
        end
        in_part = true
      elseif b.t == "Header" and b.level == 1 then
        if is_unnumbered(b) then
          in_part = false
        elseif in_part then
          b.level = 2
        end
        out[#out + 1] = b
      elseif b.t == "HorizontalRule" or is_break_para(b) then
        out[#out + 1] = scene_break()
      else
        local prev = out[#out]
        if b.t == "Para" and prev and prev.t == "Header" and #b.content == 1 and b.content[1].t == "Emph" then
          b = pandoc.Div({ b }, pandoc.Attr("", { "dateline" }))
        end
        out[#out + 1] = b
      end
    end
  end

  -- inline table of contents: Part > Chapter
  local items, cur = {}, nil
  for _, b in ipairs(out) do
    if b.t == "Header" and b.level <= 2 and not b.classes:includes("unlisted") and b.identifier ~= "" then
      local link = pandoc.Plain({ pandoc.Link(b.content, "#" .. b.identifier) })
      if b.level == 1 then
        cur = { link, {} }
        items[#items + 1] = cur
      elseif cur then
        cur[2][#cur[2] + 1] = { pandoc.Plain({ pandoc.Link(b.content, "#" .. b.identifier) }) }
      end
    end
  end
  local list = {}
  for _, it in ipairs(items) do
    local entry = { it[1] }
    if #it[2] > 0 then entry[2] = pandoc.BulletList(it[2]) end
    list[#list + 1] = entry
  end
  local toc_title = meta["toc-title"] and stringify(meta["toc-title"]) or "Contents"
  local toc_header = pandoc.Header(1, { pandoc.Str(toc_title) },
    pandoc.Attr("saga-toc", { "unnumbered", "unlisted", "toc-page" }, { { "epub:type", "toc" } }))

  local result = {}
  for _, b in ipairs(copyright) do result[#result + 1] = b end
  result[#result + 1] = toc_header
  result[#result + 1] = pandoc.Div({ pandoc.BulletList(list) }, pandoc.Attr("", { "toc-list" }))
  for _, b in ipairs(out) do result[#result + 1] = b end
  doc.blocks = result
  return doc
end
