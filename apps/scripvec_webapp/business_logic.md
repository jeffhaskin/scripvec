From the Engineer: This isn't everything, it's just stuff I said to claude design that I didn't want to leave to guess work during implementation in case it wasn't clear in the zip files.


Product

Vector-based semantic search over LDS scripture. Initial corpus: Book of Mormon + Doctrine & Covenants. Plain-language queries return the most semantically similar verses. No AI / no generated prose — retrieved verses only.
Tabs / Views
01 — Search-first

    Google-style hero with one big query field
    Results below, each showing: reference, verse text, similarity score
    Clicking any verse → opens it in the Details view (tab 04)

02 — Split pane

    Power-user view with persistent left-side filter panel
    Filters: volume (BoM, D&C), book, top-k, similarity threshold
    Results on the right
    Clicking a verse → opens Details view

03 — Research

    Turn-based query thread. Every turn is just another search — no instructional/refinement messages; each "you" bubble is a new semantic query.
    Three-column layout:
        Left: Notes & Verses list
        Center: thread of queries + verse results
        Right: Saved lists rail
    Hovering a verse in the thread reveals a Material Icons add button (top-right of verse); clicking pins it to the Notes & Verses list. Pinned state shows check icon.

04 — Details view

    The detail viewer for any verse clicked from tabs 01/02/03.
    Three-column layout:
        Left: original search results (scrollable, click any to reload the center + refresh the right pane)
        Center: the clicked verse opened in its full chapter, with the verse highlighted
        Right: "Semantically similar" panel — auto-runs a new semantic search using the current verse as the query; updates when you switch verses
    Has its own search bar at the top for starting fresh from here.

Notes & Verses list (scene 03)

    Title shows current list name + a dirty-state dot
    Items are either pinned verses (reference above, verse text below) or notes (freeform, editable inline — type directly in the item)
    Adding a note appends a new editable list item; pinning verses appends in the order they're added; order is preserved
    Remove control on hover
    Three buttons below the list: + note, save, export
    Export: downloads the list as a markdown file with verses (reference + text) and notes interleaved in list order
    Save: names the list and adds it to the right-rail saved-lists panel

Saved lists rail (right side of Research)

    Clicking a saved list loads it into the Notes & Verses panel
    Auto-save rule: if the currently loaded list is dirty AND has >0 items, clicking a saved list auto-saves the current list first, then loads the selected one

UI chrome

    All tabs persist selected tab in localStorage
    Similarity scores, highlight style, annotations, density are togglable via the Tweaks panel (design-review only, not product chrome)
