# The Eats Module

This module exists to help us:

1. Keep track of places we want to go to, and places we've been;
2. Decide together where to go, without the "you pick" standoff;
3. Remember what we ate there and what we each thought of it.

"Places" means anywhere we eat or drink: restaurants, cafés, bars, bakeries,
food trucks. Takeout and delivery count too, logged as their own kind of visit
because they change the experience.

## Principles

1. **Two of us, not one.** Each of us has our own interests and our own takes,
   both visible to the other (takes only once we've both written one). Shared
   features, like search and picking a place, use both people's input.
2. **Link out, don't copy.** Google Maps already has hours, menus, photos and
   reviews. We keep a link to it and store only what we filter, sort or map on.
3. **Freeform first.** Start with tags and free-text notes instead of fields and
   categories. Promote something to structure only once it proves useful.
4. **The model proposes, we confirm.** Nothing an LLM produces becomes a record
   until one of us confirms it.
5. **Inward-facing.** No sharing, no public pages, no notifications outside the
   app. Anything proactive is a panel on the Eats home page.

## Concepts

### Places

A place has a name, shared free-text notes, optional coordinates and links. It
can be archived. Kind ("café"), cuisine ("Georgian") and area ("Astoria") are
tags, not fields.

Whether we've been to a place is worked out from its visits, not stored.

### Links

A place keeps any number of links: Google Maps, its website, Yelp, Instagram,
reservations. The kind of link is worked out from its address. A Google Maps
link is the place's identity for spotting duplicates, and is often where its
coordinates come from.

### Interest

Each of us can mark a place as "want to go". Interest is per person and visible
to both. Places we both want rank above places only one of us wants.

### Tags

Free-form labels on places. A tag page is a list. Tags cover kind, cuisine,
area, occasions ("date night") and anything else we want to group by.

### Visits

A visit is a place, a date and a type: dine-in, takeout or delivery. It has
shared free-text notes for anything else, like cost or who came.

### Takes

Each of us writes our own take on a visit: free text plus whether we'd return.
The text stays hidden from the other person until both takes exist. "Would
return" is always visible.

### Dishes

A place has dishes. A dish can be marked "to try". Each of us gives a verdict on
a dish during a visit: loved, fine or skip. The dish board shows each person's
latest verdict, so a dish that changed over time shows the change.

### Proposals

Anything an LLM produces is a proposal: places, visits, dishes, verdicts or
links that don't exist yet. Proposals wait in an inbox until confirmed, edited
or discarded.

### Decision rounds

A round is a set of candidate places and a rule. Each of us answers privately,
and the rule decides:

- **Both swipe:** each of us says yes or no to each candidate; only places we
  both said yes to survive.
- **Propose and pick:** one of us shortlists a few places; the other picks one.

## Experiences

### Capture

- **Add by name.** Type a name, optionally with an area. The app finds the real
  place and proposes its details, tags and links.
- **Paste a link.** A Google Maps link, a restaurant's site, an article or a
  review. The link is kept on the place and its contents are read into a
  proposal. Because we both save places in Google Maps today, copying a Maps
  link is likely the most common way places get in.
- **Write it like a text message.** One box for anything: "went to the Georgian
  place last night, khachapuri was incredible, Samhita found the dumplings
  bland, want the lamb next time." It becomes a proposed visit, dishes,
  verdicts, and a take for the writer.
- **Receipt photo.** An itemized receipt becomes a proposed visit with its date
  and dishes. Only verdicts and takes are left to add. The image is discarded
  once read.
- **Inbox.** Every proposal waits here while it's being worked on and until it's
  confirmed. A pending proposal survives closing the app, and either of us can
  confirm it.

### Organize

- **Tag pages.** Every tag is a browsable list.
- **Dish board.** On each place: loved (and by whom), to try, skip.

### Decide

- **Quick pick.** A few filters, three suggestions. Weighted by interest (both
  of us, then one of us) and by how long a place has waited.
- **Random pick.** A random place from those either of us wants to go to, after
  filters.
- **Both swipe** and **propose and pick**, as decision rounds. When a round
  decides on a place, we can log it as a visit for today, which then shows up in
  the "how was it?" panel.

### After

- **Log a visit,** with its type, dishes and verdicts.
- **Separate takes, revealed together.**
- **"How was it?" panel.** Recent visits where you haven't written your take sit
  at the top of the Eats home page.

### Remember and upkeep

- **Place page.** A magazine-style page: the name, a pull quote from our notes,
  links, the dish board and the visit timeline.
- **Browse and map.** Lists by interest, tag or visit history, sorted by date
  added, last visit or how long a place has waited, with a map view.
- **Search.** Across place names, notes, dishes and takes.
- **Merge duplicates,** and a warning when adding a place we already have.

## Build Order

Each milestone is usable on its own. The first three need no LLM.

1. **Places and lists.** Places, links, tags, interest, browse, search, the
   place page and merging. Places are added by hand: a name, plus a pasted Maps
   link, which the framework browser opens to fill in the place's name and
   address. This alone replaces our Google Maps lists.
2. **Visits and dishes.** Visits, dishes and verdicts, takes with the reveal,
   and the "how was it?" panel.
3. **Deciding.** Quick pick, random pick, and decision rounds.
4. **Capture with an LLM.** Proposals and the inbox, then writing freeform,
   add by name, reading pasted links, receipt photos, and the duplicate
   warning. This is the largest milestone, because the first LLM feature brings
   in proposals.
5. **Map.** Coordinates for places and the map view.

## Later

Added when the need comes up. Most are cheap once the milestones above exist:

- **Cheap:** screenshots as capture (same as receipts), importing Google Maps
  saved lists from Google Takeout, importing a published list, an at-the-table
  layout of the place page, "where we disagree", a cleanup round where we each
  mark keep or drop on old places, and "near me" on the map.
- **Next:** asking in plain words ("cozy, not Indian, near the park"), including
  places we haven't saved; memories ("on this day"); trips, as a tag plus a
  researched shortlist for a city.
- **Bigger:** planning for occasions, watching for closed places, a written year
  in review, sharing from the phone's share sheet, and photos.

Not planned: tracking who recommended a place, menu photos (Maps has them),
tapping verdicts at the table, a lapsed-favorites panel, any sharing, and
cooking at home.

## LLM Integration

- Agents are defined in `modules/eats/llm.py` and run with the framework's
  `run_agent`, using the `default` model role. Their output types are the
  proposal's shape, as dataclasses.
- Lookup and link reading use the framework's `web_toolset` (Google search and
  page fetching in the app's own browser). Receipts are sent as images.
- Capture's results are saved as proposals, so capture runs as a queued job,
  not inside a request. The inbox checks back with HTMX until the proposal is
  ready. The proposal keeps its latest run's id, so a failure can be inspected.
- A job interrupted by a restart isn't rerun. A proposal still in progress well
  after it was queued is shown as failed, with retry.
- When a proposal concerns a place we already have, the model is given that
  place's existing dish names, so it matches dishes instead of creating
  near-duplicates.
- The model never sees a take that hasn't been revealed to both of us.
- Answers that are watched rather than saved, like asking in plain words
  (Later), run inside the request and stream their progress.

## Maps and Location

- Coordinates come from the Google Maps link when it contains them. Short links
  are opened in the framework browser to reach the full address first.
  Otherwise they come from the place's address via OpenStreetMap's Nominatim,
  at most one request per second, with an identifying user agent, as its usage
  policy requires.
- The map uses Leaflet with OpenStreetMap tiles and shows OSM's attribution.
  Leaflet is vendored into `static/js`, like HTMX.
- Opening hours are not stored. The place page links to Maps for them.

## Framework Concerns

- **Queued jobs, LLM runs and the browser** come from the framework (FR-F1 to
  FR-F3); see `docs/architecture.md`.
- **Private answers revealed together.** Takes are the first use. Current
  Affairs' quiz and reflections are the second. Build it in Eats and move it
  into the framework only once Current Affairs needs it.
- **Two users.** "Both of us" means every user account. The reveal and
  decision-round rules assume exactly two.

______________________________________________________________________

# Functional Requirements

## Framework Requirements

### FR-F1: Queued Jobs

- FR-F1.1: Modules can queue a one-off job for a module-level function, with
  arguments, without waiting for it
- FR-F1.2: A job queued while the app is down runs when it starts; a job
  interrupted by a restart is not rerun
- FR-F1.3: A job's outcome, including failure, is recorded by the module that
  queued it

### FR-F2: LLM Runs

- FR-F2.1: Modules run Pydantic AI agents by model role (`default`, `fast`);
  each role's model is set in code and can be overridden from the environment
- FR-F2.2: Every run is recorded with its agent, model, status, usage, cost,
  error and messages; runs cut off by a restart are marked interrupted
- FR-F2.3: Images in prompts are not stored in run records
- FR-F2.4: Agents can search the web and read pages through the framework
  browser, whatever the provider

### FR-F3: Browser

- FR-F3.1: The framework can open a web page in a real browser and return its
  final URL, title, main text, structured data and links
- FR-F3.2: The framework can run a Google search and return the results page's
  text and result links, and reports when the search is blocked
- FR-F3.3: Every request a page makes, including redirects and resources, is
  refused if it goes to a private, loopback or link-local address

## Module Requirements

### FR-M1: Places

- FR-M1.1: A place has a name, shared notes, optional coordinates, and an
  archived state
- FR-M1.2: Places can be created, edited, archived and merged
- FR-M1.3: Merging combines links, tags, interest, visits and dishes, and merges
  dishes with the same name
- FR-M1.4: Whether a place has been visited is worked out from its visits

### FR-M2: Links

- FR-M2.1: A place can have any number of links
- FR-M2.2: A link's kind (Google Maps, website, Yelp, Instagram, other) is
  worked out from its address
- FR-M2.3: Adding a place whose Google Maps link matches an existing place warns
  about the duplicate

### FR-M3: Interest and Tags

- FR-M3.1: Each user can mark a place as "want to go"; both users see each
  other's interest
- FR-M3.2: Places can have any number of free-form tags
- FR-M3.3: Each tag has a page listing its places

### FR-M4: Visits and Takes

- FR-M4.1: A visit has a place, a date, a type (dine-in, takeout, delivery) and
  shared notes
- FR-M4.2: Each user can write one take per visit: free text and whether they'd
  return
- FR-M4.3: A take's text is hidden from the other user until both have written a
  take; "would return" is always visible
- FR-M4.4: Takes remain editable after they're revealed
- FR-M4.5: The Eats home page lists recent visits where the current user hasn't
  written a take

### FR-M5: Dishes

- FR-M5.1: A place has dishes; a dish can be marked "to try"
- FR-M5.2: Each user can record a verdict on a dish for a visit: loved, fine or
  skip
- FR-M5.3: The dish board shows each user's latest verdict per dish

### FR-M6: Finding Places

- FR-M6.1: Places can be filtered by interest, tag and visit history
- FR-M6.2: Places can be sorted by date added, last visit and time waited
- FR-M6.3: Full-text search covers place names, notes, dish names and takes
- FR-M6.4: Search never returns the other user's unrevealed take
- FR-M6.5: Quick pick returns three places matching filters, weighted by
  interest and time waited
- FR-M6.6: Random pick returns one place either user wants to go to, after
  filters
- FR-M6.7: Places with coordinates can be shown on a map, with the same filters

### FR-M7: Decision Rounds

- FR-M7.1: Either user can start a round from a filtered set of places
- FR-M7.2: In a "both swipe" round, each user answers yes or no per candidate
  without seeing the other's answers; only places both said yes to are shown as
  results
- FR-M7.3: If a "both swipe" round has no matches, it can deal a new set of
  candidates
- FR-M7.4: In a "propose and pick" round, one user shortlists places and the
  other picks one
- FR-M7.5: A decided round can create a visit for today, by explicit submit

### FR-M8: Capture and Proposals

- FR-M8.1: Adding by name looks up the real place and proposes its details, tags
  and links
- FR-M8.2: A pasted link is kept on the place and its contents read into a
  proposal
- FR-M8.3: Freeform text becomes a proposal covering places, visits, dishes,
  verdicts and the writer's own take
- FR-M8.4: A receipt photo becomes a proposed visit with its date and dishes;
  the image is discarded once read
- FR-M8.5: Proposals are worked on in the background and wait in an inbox,
  showing their progress
- FR-M8.6: A proposal can be confirmed (with edits) or discarded; confirming
  creates all its records together
- FR-M8.7: A failed proposal shows what went wrong and can be retried

______________________________________________________________________

## Open Questions

- Is "to try" shared, or per person? Starting shared.
- How reliably do Google Maps links from our phones resolve to coordinates? To
  check with real links in milestone 1, before the map depends on it. Opening a
  Maps search page in the browser gives the place's name, rating and hours as
  text, but its address bar didn't update to the place's coordinates in a
  first test.
