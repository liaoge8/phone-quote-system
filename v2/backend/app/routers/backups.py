import hashlib
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter()
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/app/data/backups"))
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024


def _audit(db: Session, admin: User, action: str, filename: str, detail: dict | None = None):
    db.add(AuditLog(actor_id=admin.id, action=action, target_type="backup",
                    target_id=filename, detail=detail or {}))
    db.commit()


def _safe_archive(path: Path) -> dict:
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            names = {m.name for m in members}
            required = {"database.dump", "policy-evidence.tar.gz", "manifest.txt", "SHA256SUMS"}
            if not required.issubset(names):
                raise ValueError("备份包缺少必要文件")
            for member in members:
                p = Path(member.name)
                if p.is_absolute() or ".." in p.parts or not member.isfile():
                    raise ValueError("备份包包含不安全路径或非普通文件")
                if member.name not in required:
                    raise ValueError("备份包包含未识别文件")
            manifest_file = archive.extractfile("manifest.txt")
            manifest = manifest_file.read(4096).decode("utf-8")
            if "format=phone-quote-backup-v1" not in manifest.splitlines():
                raise ValueError("不支持的备份包格式")
            sums_file = archive.extractfile("SHA256SUMS")
            lines = sums_file.read(8192).decode("utf-8").splitlines()
            expected = {}
            for line in lines:
                digest, name = line.split(maxsplit=1)
                expected[name.strip().lstrip("*")] = digest
            if set(expected) != required - {"SHA256SUMS"}:
                raise ValueError("备份校验清单不完整")
            for name, digest in expected.items():
                source = archive.extractfile(name)
                actual = hashlib.sha256(source.read()).hexdigest()
                if actual != digest:
                    raise ValueError(f"备份文件校验失败：{name}")
            return {"format": "phone-quote-backup-v1", "created_at": next(
                (line.split("=", 1)[1] for line in manifest.splitlines() if line.startswith("created_at_utc=")), None
            )}
    except (tarfile.TarError, UnicodeDecodeError, KeyError, ValueError) as exc:
        raise HTTPException(422, f"备份包无效：{exc}") from exc


@router.get("")
def list_backups(admin: User = Depends(require_admin)):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(BACKUP_DIR.glob("phone-quote-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True):
        items.append({"filename": path.name, "size": path.stat().st_size,
                      "modified_at": path.stat().st_mtime,
                      "uploaded": path.name.startswith("phone-quote-upload-")})
    return items


@router.post("", status_code=201)
def create_backup(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    script = Path("/app/scripts/backup.sh")
    if not script.is_file():
        raise HTTPException(503, "备份脚本未安装，请检查 Docker 镜像")
    env = os.environ.copy()
    env["BACKUP_DIR"] = str(BACKUP_DIR)
    try:
        result = subprocess.run(["bash", str(script)], env=env, capture_output=True,
                                text=True, timeout=1800, check=True)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "备份超时，请检查数据库和证据文件") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, "备份失败：" + (exc.stderr[-1000:] if exc.stderr else "未知错误")) from exc
    filename = next((line.split(": ", 1)[1] for line in result.stdout.splitlines()
                     if line.startswith("Backup package: ")), None)
    if not filename:
        raise HTTPException(500, "备份脚本未返回备份文件名")
    path = Path(filename)
    _audit(db, admin, "backup.created", path.name, {"size": path.stat().st_size})
    return {"filename": path.name, "size": path.stat().st_size}


@router.post("/upload", status_code=201)
async def upload_backup(file: UploadFile = File(...), db: Session = Depends(get_db),
                        admin: User = Depends(require_admin)):
    if not file.filename or not file.filename.lower().endswith(".tar.gz"):
        raise HTTPException(415, "仅支持 .tar.gz 备份包")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = BACKUP_DIR / (".upload-" + uuid4().hex + ".tmp")
    total = 0
    try:
        with temp_path.open("xb") as target:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "备份包不能超过 1GB")
                target.write(chunk)
        metadata = _safe_archive(temp_path)
        filename = "phone-quote-upload-" + uuid4().hex + ".tar.gz"
        final_path = BACKUP_DIR / filename
        os.replace(temp_path, final_path)
        checksum = hashlib.sha256(final_path.read_bytes()).hexdigest()
        (BACKUP_DIR / (filename + ".sha256")).write_text(f"{checksum}  {filename}\n", encoding="utf-8")
        _audit(db, admin, "backup.uploaded", filename,
               {"size": total, "created_at": metadata.get("created_at"), "sha256": checksum})
        return {"filename": filename, "size": total, "created_at": metadata.get("created_at"),
                "message": "备份包已上传并通过内部校验；尚未恢复到当前数据库。"}
    finally:
        await file.close()
        temp_path.unlink(missing_ok=True)


@router.get("/{filename}/download")
def download_backup(filename: str, admin: User = Depends(require_admin)):
    if Path(filename).name != filename or not filename.startswith("phone-quote-") or not filename.endswith(".tar.gz"):
        raise HTTPException(400, "备份文件名无效")
    path = BACKUP_DIR / filename
    if not path.is_file():
        raise HTTPException(404, "备份文件不存在")
    return FileResponse(path, media_type="application/gzip", filename=filename)


@router.delete("/{filename}")
def delete_backup(filename: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if Path(filename).name != filename or not filename.startswith("phone-quote-") or not filename.endswith(".tar.gz"):
        raise HTTPException(400, "备份文件名无效")
    path = BACKUP_DIR / filename
    if not path.is_file():
        raise HTTPException(404, "备份文件不存在")
    path.unlink()
    (BACKUP_DIR / (filename + ".sha256")).unlink(missing_ok=True)
    _audit(db, admin, "backup.removed", filename)
    return {"message": "备份文件已删除"}
