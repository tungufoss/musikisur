-- {{< spotify ID >}} renders a green Spotify icon linking to a track.
-- {{< spotify ID type="album" >}} links to an album (or artist, playlist) instead.
-- Find IDs with: python scripts/spotify_lookup.py "Artist" "Title"

local function text(value)
  if value == nil then
    return ""
  end
  return pandoc.utils.stringify(value)
end

-- {{< spotify-player ID >}} embeds Spotify's compact player (height="152" for the large one).

return {
  ["spotify-player"] = function(args, kwargs)
    local id = text(args[1])
    if id == "" then
      error("spotify-player shortcode needs a Spotify ID")
    end
    local kind = text(kwargs["type"])
    if kind == "" then
      kind = "track"
    end
    local height = text(kwargs["height"])
    if height == "" then
      height = "80"
    end
    return pandoc.RawInline(
      "html",
      '<iframe class="spotify-player" src="https://open.spotify.com/embed/' .. kind .. "/" .. id
        .. '" width="100%" height="' .. height .. '" frameborder="0" loading="lazy" title="Spotify"'
        .. ' allow="clipboard-write; encrypted-media; fullscreen; picture-in-picture"></iframe>'
    )
  end,

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
    local embed = "https://open.spotify.com/embed/" .. kind .. "/" .. id
    -- data-spotify-embed: a click opens the compact player on the page (_spotify-inline.html).
    return pandoc.RawInline(
      "html",
      '<a href="' .. url .. '" class="spotify-link" data-spotify-embed="' .. embed .. '"'
        .. ' aria-expanded="false" title="Hlusta á Spotify" aria-label="Hlusta á Spotify">'
        .. '<i class="bi bi-spotify spotify-icon" aria-hidden="true"></i></a>'
    )
  end,
}
