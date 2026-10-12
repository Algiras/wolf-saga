-- Quarto filter for the print interior (format saga-print-pdf).
--
-- Works on the merged book document that Quarto hands to pandoc:
--   * splits "Vilko Tremtis" style subtitles ("I Knyga: Vilko Tremtis") for the title page;
--   * moves the licence chapter (copyright.qmd) into the front matter (copyright verso);
--   * drops the web-only reading-order page;
--   * places \mainmatter before the first story chapter or part, \backmatter before the
--     first unnumbered chapter after it (afterword, sources);
--   * scene breaks (--- and * * *) become one centred ornament; the dateline under a chapter
--     title (a lone emphasised paragraph) is centred.

local stringify = pandoc.utils.stringify

local COPYRIGHT = { ["Licencija"] = true, ["License"] = true, ["Licence"] = true }
local DROP = { ["Skaitymo tvarka"] = true, ["Reading order"] = true }

local function raw(s) return pandoc.RawBlock("latex", s) end

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

function Pandoc(doc)
  local meta = doc.meta

  -- title page parts
  local sub = stringify(meta.subtitle or "")
  local num, ttl = sub:match("^(.-):%s*(.+)$")
  meta["saga-booknum"] = num or ""
  meta["saga-booktitle"] = ttl or sub

  local out, copyright = {}, {}
  local mode = nil            -- "copyright" | "drop" | nil
  local in_main, in_back = false, false

  for _, b in ipairs(doc.blocks) do
    local boundary = is_file_marker(b) or is_part(b)
      or (b.t == "Header" and b.level == 1)
    if boundary then mode = nil end

    if b.t == "Header" and b.level == 1 then
      local t = stringify(b.content)
      if COPYRIGHT[t] then mode = "copyright" elseif DROP[t] then mode = "drop" end
    end

    if mode == "copyright" then
      if not (b.t == "Header" and b.level == 1) then
        if b.t == "HorizontalRule" then
          b = raw("\\par\\vspace{0.3\\baselineskip}\\noindent\\rule{\\linewidth}{0.3pt}\\par")
        end
        copyright[#copyright + 1] = b
      end
    elseif mode ~= "drop" then
      -- matter switches
      if not in_main and (is_part(b) or (b.t == "Header" and b.level == 1 and not is_unnumbered(b))) then
        out[#out + 1] = raw("\\sagamainmatter")
        in_main = true
      elseif in_main and not in_back and b.t == "Header" and b.level == 1 and is_unnumbered(b) then
        out[#out + 1] = raw("\\sagabackmatter")
        in_back = true
      end

      if b.t == "HorizontalRule" or is_break_para(b) then
        out[#out + 1] = raw("\\sagabreak{}")
      else
        -- dateline directly under a chapter title
        local prev = out[#out]
        if b.t == "Para" and prev and prev.t == "Header" and prev.level == 1
           and #b.content == 1 and b.content[1].t == "Emph" then
          local inl = { pandoc.RawInline("latex", "\\sagadateline{") }
          for _, x in ipairs(b.content[1].content) do inl[#inl + 1] = x end
          inl[#inl + 1] = pandoc.RawInline("latex", "}")
          b = pandoc.Para(inl)
        end
        out[#out + 1] = b
      end
    end
  end

  if #copyright > 0 then
    meta["saga-copyright"] = pandoc.MetaBlocks(copyright)
  end
  doc.blocks = out
  return doc
end
