-- {{< genius SONG_ID >}} embeds Genius' own lyrics widget for a song. The lyrics are loaded from
-- genius.com (served and licensed by Genius); nothing is copied into this repository.
-- SONG_ID is the data-song-id in the Embed code on the song's Genius page.
-- Optional: url="https://genius.com/..." for the link shown while the widget loads.
-- Use it on a line of its own.

local function text(value)
  if value == nil then
    return ""
  end
  return pandoc.utils.stringify(value)
end

return {
  ["genius"] = function(args, kwargs)
    local id = text(args[1])
    if id == "" then
      error("genius shortcode needs a Genius song ID")
    end
    local url = text(kwargs["url"])
    if url == "" then
      url = "https://genius.com/songs/" .. id
    end
    return pandoc.RawBlock(
      "html",
      "<div id='rg_embed_link_" .. id .. "' class='rg_embed_link genius-embed' data-song-id='" .. id .. "'>"
        .. "Textinn á <a href='" .. url .. "'>Genius</a></div>"
        .. "<script crossorigin src='https://genius.com/songs/" .. id .. "/embed.js'></script>"
    )
  end,
}
