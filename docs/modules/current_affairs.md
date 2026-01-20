# The Current Affairs Module

This module exists to help us:

1. Keep track of what's happening in the world on a regular basis;
2. Have a daily conversation prompt and news briefing, so we have stuff to talk
   about;
3. A notes section so we can keep track of what we've talked about.

## Daily Entry Structure

Each day has an "entry" with the following components:

1. **Theme**: The topic category for today's discussion (e.g., US Politics,
   Indian Politics, Economics, International Affairs, Tech)
2. **Context Links**: 3-5 links to news articles or short videos that serve as
   a primer/context for the discussion
3. **Discussion Questions**: 2-3 thought-provoking questions to guide the
   conversation
4. **Quiz**: ~5 multiple choice questions covering:
   - Factual recall from the articles
   - Opinion/takes questions (no "correct" answer - just prompts to put down a
     position without having to write much)
   - Each person takes the quiz separately (via their own logged-in session)
   - After both complete, each can view the other's answers
5. **Reflections**: Individual reflection fields for each person, free-form
   text with a pre-filled prompt to provide light structure. The intent is to
   capture what we thought at the time so we can revisit later. After both
   complete, each can view the other's reflection.
6. **In Other News** (optional): A brief section with 2-3 additional links on
   other topics for further reading after the main discussion

## Workflow

1. A scheduled job runs each morning to generate the day's entry
2. When we meet (morning or whenever), we open the day's entry
3. We review the context links together (or beforehand individually)
4. We discuss using the prompts as a guide
5. We take the quiz and record our reflections

## Topic Selection

- Themes are configurable per person (simple list, add/remove via settings)
- Daily topics are selected from the combined theme pool
- Selection primarily uses rotation to ensure variety (smart shuffle style -
  balanced without being jarring)
- However, the LLM has leeway to override rotation for genuinely significant
  events (e.g., don't talk about routine politics if someone just landed on
  Mars)
- Topics don't need to be cutting-edge news; can draw from the past week or
  month to ensure interesting discussions even on slow news days

## Content Generation

- News is fetched from free sources
- LLMs are used to:
  - Assess if there's a major event worth overriding the rotation
  - Select relevant articles for the chosen theme
  - Generate discussion questions
  - Create the quiz
  - Generate the "In Other News" brief
- Scheduled job runs at a configurable time (default: 6 AM ET) - late enough
  to catch early morning news, early enough to be ready when needed
- Generation should complete within ~10 minutes
- On failure: manual retry available (no auto-generated entry that day until
  retry succeeds)

## History

- All past entries and reflections are preserved and browsable
- Revisit what we thought about a topic at the time
- Track patterns over time (e.g., "discussed economics 12 times this month")

## Entry Lifecycle

- A new entry is generated each day automatically
- Days can be skipped (no obligation to complete every day)
- Completion is tracked per-person (two separate indicators/bubbles)
- Entries remain editable after completion
- Quiz can be retaken after discussion if desired
- If generation fails: show "No entry today" with a manual retry option

## Content Sources

- News sources should be configurable (start with free programmatic sources,
  expand later)
- Should include a mix of:
  - Factual reporting
  - Opinion pieces (other perspectives help shape our own takes)
- Video content primarily from YouTube (integration TBD)

## Framework Concerns

The following are shared concerns handled at the framework level, not specific
to this module:

- **User accounts**: Each person logs in and fills their own reflections/quiz
  answers
- **Settings**: DB-backed configuration with UI (not config files) so non-
  technical users can adjust themes, generation time, etc.

---

# Functional Requirements

## Framework Requirements

These are shared infrastructure concerns that this module depends on but are
not specific to Current Affairs.

### FR-F1: User Authentication

- FR-F1.1: Users can log in with individual accounts
- FR-F1.2: Sessions persist across browser restarts
- FR-F1.3: All user-generated content (quiz answers, reflections) is associated
  with the logged-in user

### FR-F2: Settings Infrastructure

- FR-F2.1: Settings are stored in the database
- FR-F2.2: Settings are editable via a UI
- FR-F2.3: Modules can register their own settings (e.g., this module registers
  "generation time", "themes")

### FR-F3: Scheduled Jobs Infrastructure

- FR-F3.1: Framework supports registering scheduled jobs
- FR-F3.2: Jobs can be configured with a time of day (e.g., 6 AM ET)
- FR-F3.3: Failed jobs can be manually retried via UI

---

## Module Requirements

### FR-M1: Daily Entry Generation

- FR-M1.1: System generates one entry per day via scheduled job
- FR-M1.2: Generation runs at a configurable time (default: 6 AM ET)
- FR-M1.3: Each entry contains:
  - A theme (from the configured theme pool)
  - 3-5 context links (articles/videos)
  - 2-3 discussion questions
  - ~5 multiple choice quiz questions
  - An "In Other News" section with 2-3 additional links
- FR-M1.4: If generation fails, the day shows "No entry today" with a retry
  button
- FR-M1.5: Manual retry triggers regeneration for the current day

### FR-M2: Theme Management

- FR-M2.1: Each user can configure their own list of themes
- FR-M2.2: Themes can be added and removed via settings UI
- FR-M2.3: Daily topic is selected from the combined pool of both users' themes

### FR-M3: Topic Selection

- FR-M3.1: Topics rotate through themes to ensure variety (smart shuffle)
- FR-M3.2: System tracks which themes have been used recently to avoid
  repetition
- FR-M3.3: LLM can override rotation for significant breaking events
- FR-M3.4: Topics can draw from news up to a month old (not just today's news)

### FR-M4: Content Sourcing

- FR-M4.1: News is fetched from configurable sources
- FR-M4.2: Sources include a mix of factual reporting and opinion pieces
- FR-M4.3: Video content is sourced from YouTube
- FR-M4.4: LLM selects and curates relevant content for the chosen theme

### FR-M5: Quiz System

- FR-M5.1: Quiz consists of ~5 multiple choice questions
- FR-M5.2: Questions include both factual recall and opinion/takes
- FR-M5.3: Each user takes the quiz independently
- FR-M5.4: Quiz answers are saved per-user
- FR-M5.5: Users can retake the quiz (answers are updated, not appended)
- FR-M5.6: After both users complete the quiz, each can view the other's
  answers

### FR-M6: Reflection System

- FR-M6.1: Each user has their own reflection field per entry
- FR-M6.2: Reflection field shows a pre-filled prompt for light structure
- FR-M6.3: Reflections are free-form text
- FR-M6.4: Reflections can be edited after submission
- FR-M6.5: After both users submit reflections, each can view the other's

### FR-M7: Entry Lifecycle & Completion

- FR-M7.1: Completion is tracked per-user (two independent indicators)
- FR-M7.2: A user is marked "complete" when they have submitted quiz answers
  and a reflection
- FR-M7.3: Entries remain editable after completion
- FR-M7.4: Days without entries (skipped or failed generation) are allowed

### FR-M8: Entry Browsing & History

- FR-M8.1: Module homepage shows a reverse-chronological feed of entries
- FR-M8.2: Feed displays date and theme for each entry
- FR-M8.3: Feed shows completion status for both users per entry
- FR-M8.4: Users can navigate to any past entry
- FR-M8.5: Past entries display all content including both users' quiz answers
  and reflections
- FR-M8.6: System tracks theme usage patterns (e.g., "discussed economics 12
  times this month")

