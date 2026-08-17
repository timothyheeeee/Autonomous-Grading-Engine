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

Optional: set `OPENAI_API_KEY` in `backend/.env` to use GPT-4o vision on the rubric screenshot. Without a key, the screenshot is quality-checked and criterion labels are bound from the CSV.

## Sample files

- `backend/data/sample_peer_reviews.csv`
- Generate a rubric PNG (run from `backend` with the venv active):

```powershell
.\.venv\Scripts\python.exe -c "from PIL import Image, ImageDraw; im=Image.new('RGB',(900,640),'white'); d=ImageDraw.Draw(im); y=40
for t in ['Group Project Rubric','Scale 1-5','Collaboration','Communication','Technical Implementation','Data Wrangling','Reproducibility']:
 d.text((40,y),t,fill='black'); y+=48
im.save('data/sample_rubric.png')"
```
