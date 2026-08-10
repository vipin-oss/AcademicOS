# APPLY STEPS — AcademicOS M21 Final (Chat 404 Fix + AI Feature Flags)

## ROOT CAUSE
The 404 is NOT a bug — the `/ai/chat` route exists and is registered correctly.
It returns 404 because `AI_CHAT_ENABLED` defaults to `false`. You must enable it.

## FILES (5)
1. `frontend/src/app/(main)/chat/page.tsx` — chat page (NEW)
2. `frontend/src/components/layout/Sidebar.tsx` — AI Chat nav link (MODIFIED)
3. `frontend/src/lib/api/ai.ts` — AI API client functions (MODIFIED)
4. `frontend/src/types/index.ts` — AI response types (MODIFIED)
5. `backend/.env.example` — AI feature flags documentation (MODIFIED)

## PowerShell — copy and paste ALL of this:

```powershell
cd E:\AcademicOS

# --- 1. Extract the ZIP ---
Expand-Archive academicOS-m21-final.zip -DestinationPath C:\temp\m21f

# --- 2. Copy frontend files (use -LiteralPath for (main) directory) ---
New-Item -ItemType Directory -Force "frontend\src\app\(main)\chat" | Out-Null
Copy-Item -LiteralPath "C:\temp\m21f\academicOS-m21-final\files\frontend\src\app\(main)\chat\page.tsx" -Destination "frontend\src\app\(main)\chat\page.tsx" -Force
Copy-Item -LiteralPath "C:\temp\m21f\academicOS-m21-final\files\frontend\src\components\layout\Sidebar.tsx" -Destination "frontend\src\components\layout\Sidebar.tsx" -Force
Copy-Item -LiteralPath "C:\temp\m21f\academicOS-m21-final\files\frontend\src\lib\api\ai.ts" -Destination "frontend\src\lib\api\ai.ts" -Force
Copy-Item -LiteralPath "C:\temp\m21f\academicOS-m21-final\files\frontend\src\types\index.ts" -Destination "frontend\src\types\index.ts" -Force

# --- 3. Copy backend .env.example ---
Copy-Item "C:\temp\m21f\academicOS-m21-final\files\backend\.env.example" -Destination "backend\.env.example" -Force

# --- 4. CRITICAL: Enable AI_CHAT_ENABLED in your backend .env ---
# Check if AI_CHAT_ENABLED is already in .env:
$envContent = Get-Content "backend\.env" -Raw -ErrorAction SilentlyContinue
if ($envContent -notmatch "AI_CHAT_ENABLED") {
    # Append the AI flags to .env
    Add-Content "backend\.env" ""
    Add-Content "backend\.env" "# AI Core feature flags"
    Add-Content "backend\.env" "AI_ENABLED=true"
    Add-Content "backend\.env" "AI_CHAT_ENABLED=true"
    Add-Content "backend\.env" "AI_STREAMING_ENABLED=true"
    Write-Host "Added AI_CHAT_ENABLED=true to backend\.env"
} else {
    Write-Host "AI_CHAT_ENABLED already exists in .env — please set it to true"
}

# --- 5. Restart the backend (Ctrl+C in the backend terminal, then) ---
# cd backend
# python -m uvicorn app.main:app --reload --port 8000

# --- 6. Verify frontend tests ---
cd frontend
npm run test -- --run
npm run build
npx tsc --noEmit

# --- 7. Commit and push ---
cd E:\AcademicOS
git add "frontend/src/app/(main)/chat/page.tsx" frontend/src/components/layout/Sidebar.tsx frontend/src/lib/api/ai.ts frontend/src/types/index.ts backend/.env.example
git commit -m "feat(m21): frontend AI chat UI + fix 404 by enabling feature flag"
git push origin feature/m11-ai-workspace
```
