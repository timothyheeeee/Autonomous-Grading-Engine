# Autonomous Group Assignment & Capability Tracking

Drop a peer-review CSV and a rubric screenshot. A three-brain LangGraph pipeline reads the image, extracts the team from the CSV, and converts every score into a **percentage**. Nothing is saved until you approve.

The UI starts empty. There is no preloaded roster.

## Run

Backend:

```powershell
cd "C:\Users\Timothy\Desktop\Adv AI Project\backend"
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd "C:\Users\Timothy\Desktop\Adv AI Project\frontend"
npm install
npm run dev
```

Open http://localhost:3000

Set `OPENAI_API_KEY` in `backend/.env` before uploading. Rubric verification calls the vision model and will not invent criteria when the key is missing or the request fails. Restart the backend after changing the key.

The pipeline checks meaning, not only the file type:

- The screenshot must be a readable grading rubric with real criteria and a scoring scale. Photos, receipts, and unrelated screenshots are rejected.
- The CSV must identify a student and contain task or peer-feedback text. Inventory, weather, and employee tables are rejected. Column names can vary (`Student`, `Reviewee`, `Team Member`, `Tasks Completed`, `Peer Feedback`).
- Each score must use 0, 5, or 10, name a student from the CSV, use a criterion from the rubric, and be supported by that review. Invalid results stop before calculation and are not published.

Nothing is saved until you approve the percentages.

## Sample files

- `backend/data/sample_peer_reviews.csv`
- Generate a rubric PNG (run from `backend` with the venv active):

```powershell
.\.venv\Scripts\python.exe -c "from PIL import Image, ImageDraw; im=Image.new('RGB',(900,640),'white'); d=ImageDraw.Draw(im); y=40
for t in ['Group Project Rubric','Scale 1-5','Collaboration','Communication','Technical Implementation','Data Wrangling','Reproducibility']:
 d.text((40,y),t,fill='black'); y+=48
im.save('data/sample_rubric.png')"
```
