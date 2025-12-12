# Frontend/Backend Restructure Options

## Current Situation
- **Frontend**: Next.js app in `frontend/` directory
- **Backend**: FastAPI app in `web_app/` directory  
- **Data Collection**: Scripts in `src/` and root
- **Config**: YAML file in `config/`

## Option 1: Minimal Separation (Recommended for Quick Fix)
```
nsw_suburb_finder/
├── backend/              # All Python backend code
│   ├── api/             # FastAPI app (from web_app/)
│   ├── data/            # Data collectors (from src/data/)
│   ├── analysis/        # Scoring engine (from src/analysis/)
│   └── scripts/         # Collection scripts (from root)
├── frontend/            # Next.js (unchanged)
├── config/              # Config files (unchanged)
└── requirements.txt
```
**Pros**: Simple, minimal changes, clear frontend/backend split  
**Cons**: Still some mixing of concerns within backend

---

## Option 2: Clean Architecture (Best for Long-term)
```
nsw_suburb_finder/
├── backend/
│   ├── api/             # FastAPI routes & models
│   ├── services/        # Business logic
│   ├── repositories/   # Data access
│   ├── data/            # Data collection
│   └── core/            # Config, database
├── frontend/            # Next.js (unchanged)
├── config/              # Config files
└── requirements.txt
```
**Pros**: Clean separation, testable, scalable  
**Cons**: More refactoring needed

---

## Option 3: Monorepo Style (Keep Current + Organize)
```
nsw_suburb_finder/
├── apps/
│   ├── api/             # FastAPI backend (from web_app/)
│   └── web/              # Next.js frontend (from frontend/)
├── packages/
│   ├── data-collectors/  # Data collection logic
│   ├── scoring/          # Analysis/scoring
│   └── shared/           # Shared types/config
├── config/
└── requirements.txt
```
**Pros**: Clear apps vs packages separation  
**Cons**: More complex structure

---

## Option 4: Keep It Simple (Minimal Changes)
Just rename directories:
- `web_app/` → `backend/`
- Keep `frontend/` as is
- Keep `src/` as is
- Remove `create_web_app.py` (redundant)

**Pros**: Easiest, minimal disruption  
**Cons**: Still has mixed concerns

---

## My Recommendation

**Option 1** is the sweet spot:
- Clear frontend/backend separation
- Easy to understand
- Minimal refactoring
- Good enough for most projects

Which option do you prefer? Or want me to suggest a different approach?
