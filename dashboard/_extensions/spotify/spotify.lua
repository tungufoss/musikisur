-- {{< spotify ID >}} renders a green Spotify icon linking to a track.
-- {{< spotify ID type="album" >}} links to an album (or artist, playlist) instead.
-- Find IDs with: python scripts/spotify_lookup.py "Artist" "Title"

local function text(value)
  if value == nil then
    return ""
  end
  return pandoc.utils.stringify(value)
end

return {
  ["spotify"] = function(args, kwargs)
    local id = text(args[1])
    if id == "" then
      error("spotify shortcode needs a Spotify ID")
    end
    local kind = text(kwargs["type"])
    if kind == "" then
      kind = "track"
    end
    local url = "https://open.spotify.com/" .. kind .. "/" .. id
    return pandoc.RawInline(
      "html",
      '<a href="' .. url .. '" class="spotify-link" title="Hlusta á Spotify" aria-label="Hlusta á Spotify">'
        .. '<i class="bi bi-spotify spotify-icon" aria-hidden="true"></i></a>'
    )
  end,
}
