#!/bin/bash
# Comprehensive API test script for AI Workflow Terminal v0.8
BASE="http://localhost:8000"
PASS=0
FAIL=0

check() {
    local name="$1" expected="$2" actual="$3"
    if echo "$actual" | grep -q "$expected"; then
        echo "  [PASS] $name"
        PASS=$((PASS+1))
    else
        echo "  [FAIL] $name (expected '$expected', got: $actual)"
        FAIL=$((FAIL+1))
    fi
}

echo "=============================="
echo "  AI Workflow Terminal v0.8"
echo "  Comprehensive API Tests"
echo "=============================="

# --- TEST 1: Health ---
echo ""
echo "--- Test 1: Health Check ---"
R=$(curl -s $BASE/health)
check "health endpoint" '"status":"ok"' "$R"

# --- TEST 2: Auth ---
echo ""
echo "--- Test 2: Auth Module ---"

R=$(curl -s -X POST $BASE/api/auth/register -H "Content-Type: application/json" \
    -d '{"username":"testuser","email":"test@example.com","password":"TestPass123"}')
check "register user" '"username":"testuser"' "$R"

R=$(curl -s -X POST $BASE/api/auth/login -H "Content-Type: application/json" \
    -d '{"username":"testuser","password":"TestPass123"}')
check "login" '"access_token"' "$R"
TOKEN=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "  [FATAL] No token received, cannot continue tests"
    exit 1
fi
AUTH="Authorization: Bearer $TOKEN"

R=$(curl -s $BASE/api/auth/me -H "$AUTH")
check "get current user" '"username":"testuser"' "$R"

# Duplicate register
R=$(curl -s -X POST $BASE/api/auth/register -H "Content-Type: application/json" \
    -d '{"username":"testuser","email":"test2@example.com","password":"TestPass123"}')
check "duplicate username rejected" '"detail"' "$R"

# --- TEST 3: Engines ---
echo ""
echo "--- Test 3: Engine Registry ---"

R=$(curl -s $BASE/api/engines -H "$AUTH")
check "list engines" '"engines"' "$R"

R=$(curl -s $BASE/api/engines/capabilities -H "$AUTH")
check "capabilities" '"capabilities"' "$R"

# --- TEST 4: Memory ---
echo ""
echo "--- Test 4: Memory Module ---"

R=$(curl -s -X POST $BASE/api/memory/save -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"content":"User prefers dark mode","category":"preference"}')
check "save memory" '"status"' "$R"

R=$(curl -s -X POST $BASE/api/memory/save -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"content":"User name is Wang Qi","category":"fact"}')
check "save memory 2" '"status"' "$R"

R=$(curl -s -X POST $BASE/api/memory/search -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"query":"dark mode","top_k":5}')
check "search memory" '"results"' "$R"

R=$(curl -s $BASE/api/memory/context -H "$AUTH")
check "get context" '"context"' "$R"

# --- TEST 5: RAG ---
echo ""
echo "--- Test 5: RAG Knowledge Base ---"

R=$(curl -s -X POST $BASE/api/rag/ingest -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"content":"AI Workflow Terminal is a multi-tier system with cloud, edge, and GPU tiers. It supports 24 engines for various AI tasks.","filename":"architecture.txt"}')
check "ingest document" '"doc_id"' "$R"

R=$(curl -s -X POST $BASE/api/rag/query -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"query":"how many engines","top_k":3}')
check "query knowledge" '"results"' "$R"

R=$(curl -s $BASE/api/rag/documents -H "$AUTH")
check "list documents" '"documents"' "$R"

R=$(curl -s $BASE/api/rag/stats -H "$AUTH")
check "rag stats" '"documents"' "$R"

# --- TEST 6: Workflow ---
echo ""
echo "--- Test 6: Workflow Engine ---"

R=$(curl -s -X POST $BASE/api/workflow/create -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"name":"Test Workflow","definition":{"workflow":{"steps":[{"id":"step_1","step_type":"transform","mapping":{"result":"hello world"}}]}},"description":"A test workflow"}')
check "create workflow" '"id"' "$R"
WF_ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)

R=$(curl -s $BASE/api/workflow/list -H "$AUTH")
check "list workflows" '"workflows"' "$R"

R=$(curl -s -X POST $BASE/api/workflow/validate -H "Content-Type: application/json" \
    -d '{"definition":{"workflow":{"steps":[{"id":"s1","step_type":"engine","engine":"llm","action":"chat"}]}}}')
check "validate workflow" '"valid":true' "$R"

if [ -n "$WF_ID" ]; then
    R=$(curl -s -X POST "$BASE/api/workflow/$WF_ID/execute" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"input_data":{"x":1}}')
    check "execute workflow" '"status"' "$R"

    R=$(curl -s "$BASE/api/workflow/$WF_ID/history" -H "$AUTH")
    check "workflow history" '"history"' "$R"
fi

R=$(curl -s $BASE/api/workflow/stats -H "$AUTH")
check "workflow stats" '"total_workflows"' "$R"

# --- TEST 7: DocVersion ---
echo ""
echo "--- Test 7: Document Version Management ---"

R=$(curl -s -X POST $BASE/api/docs/ingest -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"content":"# Project Requirements\n\n## Functional Requirements\n1. User authentication\n2. AI chat interface","title":"Requirements Doc","project":"project_alpha","doc_type":"requirements"}')
check "ingest document v1" '"action":"created"' "$R"
DOC_ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('doc_id',''))" 2>/dev/null)

# Ingest same filename again (should update)
R=$(curl -s -X POST $BASE/api/docs/ingest -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"content":"# Project Requirements\n\n## Functional Requirements\n1. User authentication\n2. AI chat interface\n3. Workflow engine","title":"Requirements Doc v2","source_file":"requirements.md","project":"project_alpha"}')
check "ingest document v2" '"action":"created"' "$R"

R=$(curl -s $BASE/api/docs/list -H "$AUTH")
check "list documents" '"documents"' "$R"

R=$(curl -s $BASE/api/docs/recent -H "$AUTH")
check "recent documents" '"documents"' "$R"

R=$(curl -s "$BASE/api/docs/search?type=requirements" -H "$AUTH")
check "search by type" '"documents"' "$R"

if [ -n "$DOC_ID" ]; then
    R=$(curl -s "$BASE/api/docs/$DOC_ID" -H "$AUTH")
    check "get document" '"doc_id"' "$R"

    R=$(curl -s "$BASE/api/docs/$DOC_ID/latest" -H "$AUTH")
    check "get latest content" '"content"' "$R"

    R=$(curl -s "$BASE/api/docs/$DOC_ID/history" -H "$AUTH")
    check "version history" '"history"' "$R"
fi

R=$(curl -s $BASE/api/docs/projects -H "$AUTH")
check "list projects" '"projects"' "$R"

R=$(curl -s $BASE/api/docs/stats -H "$AUTH")
check "doc stats" '"documents"' "$R"

# --- TEST 8: Task System ---
echo ""
echo "--- Test 8: Task Management ---"

R=$(curl -s -X POST $BASE/api/tasks -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"title":"Analyze Sales Data","description":"Analyze Q1 sales data and generate report","priority":"high","category":"data_analysis","tags":["sales","q1"]}')
check "create task" '"task_id"' "$R"
TASK_ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null)

R=$(curl -s "$BASE/api/tasks" -H "$AUTH")
check "list tasks" '"tasks"' "$R"

if [ -n "$TASK_ID" ]; then
    R=$(curl -s "$BASE/api/tasks/$TASK_ID" -H "$AUTH")
    check "get task" '"status":"draft"' "$R"

    R=$(curl -s -X POST "$BASE/api/tasks/$TASK_ID/transition" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"target_status":"sent","message":"Sending to team"}')
    check "transition draft->sent" '"status":"sent"' "$R"

    R=$(curl -s -X POST "$BASE/api/tasks/$TASK_ID/transition" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"target_status":"received"}')
    check "transition sent->received" '"status":"received"' "$R"

    R=$(curl -s -X POST "$BASE/api/tasks/$TASK_ID/transition" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"target_status":"accepted"}')
    check "transition received->accepted" '"status":"accepted"' "$R"

    R=$(curl -s -X POST "$BASE/api/tasks/$TASK_ID/transition" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"target_status":"in_progress","message":"Starting work"}')
    check "transition accepted->in_progress" '"status":"in_progress"' "$R"

    # Invalid transition
    R=$(curl -s -X POST "$BASE/api/tasks/$TASK_ID/transition" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"target_status":"closed"}')
    check "reject invalid transition" '"error"' "$R"

    R=$(curl -s -X POST "$BASE/api/tasks/$TASK_ID/progress" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"percentage":50,"description":"Data collected","milestone":"Collection"}')
    check "update progress" '"progress"' "$R"

    R=$(curl -s -X POST "$BASE/api/tasks/$TASK_ID/messages" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"content":"Need access to CRM database","msg_type":"text_message"}')
    check "add message" '"message_id"' "$R"

    R=$(curl -s "$BASE/api/tasks/$TASK_ID/messages" -H "$AUTH")
    check "get messages" '"messages"' "$R"

    R=$(curl -s -X POST "$BASE/api/tasks/$TASK_ID/result" -H "$AUTH" -H "Content-Type: application/json" \
        -d '{"summary":"Report complete","details":"Q1 sales up 15%","deliverables":["report.pdf"]}')
    check "submit result" '"result"' "$R"
fi

R=$(curl -s "$BASE/api/tasks/stats" -H "$AUTH")
check "task stats" '"total"' "$R"

# Search
R=$(curl -s -X POST "$BASE/api/tasks/search" -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"query":"sales"}')
check "search tasks" '"tasks"' "$R"

# Templates
R=$(curl -s -X POST "$BASE/api/tasks/templates" -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"name":"Data Analysis Template","task_body":{"title":"Analyze Data","priority":"medium","category":"data_analysis"}}')
check "create template" '"template_id"' "$R"

R=$(curl -s "$BASE/api/tasks/templates" -H "$AUTH")
check "list templates" '"templates"' "$R"

# --- TEST 9: Services ---
echo ""
echo "--- Test 9: Utility Services ---"

# Crawler
R=$(curl -s -X POST $BASE/api/crawl -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"url":"https://httpbin.org/html","max_chars":1000}')
check "crawl page" '"text"' "$R"

# Email inbox
R=$(curl -s $BASE/api/email/inbox -H "$AUTH")
check "email inbox" '"emails"' "$R"

R=$(curl -s $BASE/api/email/demo_1 -H "$AUTH")
check "get email" '"subject"' "$R"

# Email send (demo mode)
R=$(curl -s -X POST $BASE/api/email/send -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"to":"bob@example.com","subject":"Test","body":"Hello Bob"}')
check "send email (demo)" '"demo_mode"' "$R"

# Translation detect
R=$(curl -s -X POST $BASE/api/translate/detect -H "Content-Type: application/json" \
    -d '{"text":"Hello world"}')
check "detect language" '"language":"en"' "$R"

R=$(curl -s -X POST $BASE/api/translate/detect -H "Content-Type: application/json" \
    -d '{"text":"\u4f60\u597d\u4e16\u754c"}')
check "detect Chinese" '"language":"zh"' "$R"

R=$(curl -s $BASE/api/translate/languages)
check "list languages" '"languages"' "$R"

# TTS voices
R=$(curl -s $BASE/api/tts/voices)
check "list voices" '"voices"' "$R"

# --- TEST 10: File Transfer ---
echo ""
echo "--- Test 10: File Transfer ---"

# Upload a file
R=$(curl -s -X POST $BASE/api/files/upload -H "$AUTH" \
    -F "file=@test_all.sh" -F "category=test")
check "upload file" '"file_id"' "$R"
FILE_ID=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('file_id',''))" 2>/dev/null)

R=$(curl -s $BASE/api/files -H "$AUTH")
check "list files" '"files"' "$R"

R=$(curl -s $BASE/api/files/stats -H "$AUTH")
check "file stats" '"total_files"' "$R"

if [ -n "$FILE_ID" ]; then
    R=$(curl -s -o /dev/null -w "%{http_code}" $BASE/api/files/$FILE_ID -H "$AUTH")
    if [ "$R" = "200" ]; then
        echo "  [PASS] download file"
        PASS=$((PASS+1))
    else
        echo "  [FAIL] download file (HTTP $R)"
        FAIL=$((FAIL+1))
    fi

    R=$(curl -s -X DELETE $BASE/api/files/$FILE_ID -H "$AUTH")
    check "delete file" '"status":"deleted"' "$R"
fi

# --- TEST 11: System Monitor ---
echo ""
echo "--- Test 11: System Monitor ---"

R=$(curl -s $BASE/api/system/status -H "$AUTH")
check "system status" '"cpu"' "$R"
check "system has memory" '"memory"' "$R"
check "system has disk" '"disk"' "$R"

R=$(curl -s $BASE/api/system/quick -H "$AUTH")
check "quick stats" '"cpu_percent"' "$R"

# --- TEST 12: Engines ---
echo ""
echo "--- Test 12: Engine Registry ---"
R=$(curl -s $BASE/api/engines -H "$AUTH")
check "engines list has llm" '"llm"' "$R"

R=$(curl -s $BASE/api/engines/health -H "$AUTH")
check "engine health" '"status"' "$R"

# --- SUMMARY ---
echo ""
echo "=============================="
echo "  Test Results: $PASS passed, $FAIL failed"
echo "=============================="
