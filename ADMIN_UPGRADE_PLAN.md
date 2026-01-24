# Admin Panel Upgrade Plan

## Current State ✅
- Basic calendar view with appointments
- CRUD operations for appointments
- Service type filters
- Patient name search
- Stats badges (pending, confirmed, today, this week)

## Target State 🎯
Match Turistična Kmetija functionality:

### 1. Tab Navigation
```
[Rezervacije] | [Orodja & Analitika]
```

### 2. Tab: Rezervacije (Current + Enhanced)
- ✅ Calendar + day schedule
- ✅ Pending section on top
- ✅ Service type filters
- ✅ Search by name
- 🆕 Communication panel in edit modal (right side)
  - Guest messages / My responses
  - Newest on top
  - Reply functionality

### 3. Tab: Orodja & Analitika (New)

#### IMAP Polling Section
- Status indicator (✅ Connected / ❌ Error)
- Last poll time
- Messages processed count
- Preview button
- Resync button

#### Analytics Widgets
- **Usage Stats**
  - Total sessions
  - Conversion rate
  - Avg session duration

- **Najpogostejša Vprašanja**
  - Top 10 questions
  - Count per question

- **Conversion Funnel**
  - Started → Completed → Confirmed
  - Percentages

- **Lost Intents**
  - Queries that didn't get good answers
  - Suggestions for improvement

- **Missed Questions**
  - Questions chatbot couldn't handle
  - Feedback system

## Implementation Steps

### Step 1: Create Tab Structure
- Add tab navigation HTML
- Add tab switching JavaScript
- Move current calendar to "Rezervacije" tab

### Step 2: Add Analytics Tab
- Create analytics.html section
- Add widget cards
- Connect to existing API endpoints:
  - `/api/admin/usage_stats`
  - `/api/admin/question_stats`
  - `/api/admin/lost_intents`
  - `/api/admin/funnel_stats`
  - `/api/admin/missed_questions`

### Step 3: IMAP Status Widget
- Connect to IMAP polling service
- Show status/errors
- Add preview/resync buttons

### Step 4: Communication in Modal
- Add message panel to edit modal
- Fetch conversation history per appointment
- Add reply functionality

## Files to Modify
1. ✏️ `static/admin_new.html` - Add tabs + analytics
2. ✏️ `app/services/admin_router.py` - Add IMAP status endpoint (if needed)
3. 🆕 Create minimal analytics widgets

## Design Consistency
- Use existing CSS variables
- Match current color scheme (teal/cyan primary)
- Keep mobile responsive
- Maintain current UX patterns

## Priority
1. **HIGH**: Tab structure + Analytics tab skeleton
2. **MEDIUM**: Analytics widgets with real data
3. **LOW**: Communication in modal (requires message tracking DB)
