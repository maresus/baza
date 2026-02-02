#!/bin/bash
# Test script za nove API endpointe

BASE_URL="${1:-http://localhost:8000}"

echo "🧪 Testing new API endpoints..."
echo "Base URL: $BASE_URL"
echo ""

# Analytics
echo "📊 Analytics Dashboard:"
curl -s "$BASE_URL/api/admin/analytics/dashboard?days=7" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  - Trending topics: {len(d.get(\"trending_topics\",{}).get(\"topics\",[]))} found')"

# Scheduler
echo ""
echo "📅 Smart Scheduler:"
curl -s "$BASE_URL/api/admin/scheduler/weekly-load" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  - Weekly load: {len(d.get(\"days\",[]))} days')"

# Knowledge Graph
echo ""
echo "🧠 Knowledge Graph:"
curl -s "$BASE_URL/api/admin/knowledge-graph/stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  - Nodes: {d.get(\"total_nodes\",0)}, Edges: {d.get(\"total_edges\",0)}')"

# Triage
echo ""
echo "🏥 Triage:"
curl -s -X POST "$BASE_URL/api/admin/triage/quick?symptoms=boli%20me%20koleno" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  - Specialist: {d.get(\"specialist\",\"N/A\")}')"

# Reminder Stats
echo ""
echo "🔔 Reminder Stats:"
curl -s "$BASE_URL/api/admin/analytics/reminder-stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  - Total: {d.get(\"total_appointments\",0)}, No-show rate: {d.get(\"no_show_rate\",0)}%')"

echo ""
echo "✅ All tests completed!"
