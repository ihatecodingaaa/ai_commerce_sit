import os, subprocess, uuid, time
from pathlib import Path
from fastapi import FastAPI, File, Header, HTTPException, UploadFile

app = FastAPI(title="Synthetic Image Management Service")
TOKEN = os.getenv("SERVICE_TOKEN", "lab_service_token_only_8f3d2a7c")
UPLOADS = Path("/app/uploads")


def log(event: str, detail: str = ""):
    safe = detail.replace(TOKEN, TOKEN[:4] + "...redacted")
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} request={uuid.uuid4()} event={event} {safe}", flush=True)


def auth(authorization: str | None):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "invalid service credential")


@app.get("/api/images")
def list_images(authorization: str | None = Header(default=None)):
    auth(authorization)
    return {"service_identity":"support-image-service","files":[p.name for p in UPLOADS.glob("*") if p.is_file()]}


@app.post("/api/images/upload")
async def upload(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    auth(authorization)
    name = Path(file.filename or "upload.bin").name
    # INTENTIONAL CTF VULNERABILITY:
    # API only checks the final extension, while the downstream processor interprets
    # compound names containing `.py.` as Python jobs. Components disagree about safety.
    if not name.lower().endswith((".jpg", ".jpeg", ".png")):
        raise HTTPException(400, "image extension required")
    data = await file.read()
    if len(data) > 128_000:
        raise HTTPException(413, "file too large")
    dest = UPLOADS / name
    dest.write_bytes(data)
    log("image_upload", name)
    result = {"stored":name,"processor":"image-metadata"}
    if ".py." in name.lower():
        # Deliberately vulnerable execution path, constrained to this disposable container.
        proc = subprocess.run(["python3", str(dest)], capture_output=True, text=True, timeout=5, cwd=str(UPLOADS))
        log("code_execution", f"file={name} uid={os.getuid()}")
        result.update({"executed_as":"appuser","stdout":proc.stdout[-4000:],"stderr":proc.stderr[-2000:],"returncode":proc.returncode,"flag":"FLAG{application_user}"})
    return result


@app.get("/health")
def health():
    return {"ok":True,"uid":os.getuid()}
