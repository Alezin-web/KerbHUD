"""Atualização pelo próprio programa, a partir dos *Releases* de um repositório público do GitHub (sem Qt).

Fluxo: consulta `releases/latest` -> compara a versão -> baixa o .zip do release -> confere o SHA-256 (se o release
tiver o arquivo `.sha256`) -> extrai com proteção contra caminhos maliciosos -> confere que parece o KerbHUD ->
copia por cima do programa. A pasta `dados` (logos, flags, badges, layouts, tracks) NUNCA é tocada e tudo o que for
substituído antes vai para `.backup/`. Só fala com github.com (HTTPS). Não executa nada baixado, exceto, no .exe, um
.bat curto gerado aqui que troca os arquivos depois que o programa fecha.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

API = "https://api.github.com/repos/{repo}/releases/latest"
ALLOWED_HOSTS = ("github.com", "api.github.com", "githubusercontent.com")  # inclui subdomínios
MAX_DOWNLOAD = 300 * 1024 * 1024
MAX_UNPACKED = 600 * 1024 * 1024
MAX_FILES = 20000
#: nunca copiados do zip nem sobrescritos
PROTECTED = {"dados", ".backup", ".git", ".github", "__pycache__", "_update"}
DEFAULT_REPO = "Alezin-web/KerbHUD"  # repositório oficial; usado quando o campo "Repositório" das configurações está vazio
_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


class UpdateError(Exception):
    """Falha esperada (sem internet, release estranho, arquivo corrompido...): a mensagem é para o usuário."""


@dataclass
class ReleaseInfo:
    version: str
    notes: str
    asset_name: str
    asset_url: str
    sha256_url: str = ""
    size: int = 0


def valid_repo(text: str) -> bool:
    return bool(_REPO.match(text or "")) and not any(set(p) <= {"."} for p in text.split("/"))


def effective_repo(settings) -> str:
    """O repositório configurado pelo usuário ou, se vazio, o oficial (assim a atualização funciona sem configurar nada)."""
    raw = str((settings or {}).get("update_repo") or "").strip()
    return raw or DEFAULT_REPO


def parse_version(text: str) -> tuple[int, ...]:
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", str(text or ""))
    if not m:
        raise ValueError(f"versão inválida: {text!r}")
    return tuple(int(x) for x in m.group(1).split("."))


def is_newer(remote: str, local: str) -> bool:
    a, b = list(parse_version(remote)), list(parse_version(local))
    n = max(len(a), len(b))
    return a + [0] * (n - len(a)) > b + [0] * (n - len(b))


def host_allowed(url: str) -> bool:
    u = urllib.parse.urlparse(url)
    h = (u.hostname or "").lower()
    return u.scheme == "https" and any(h == d or h.endswith("." + d) for d in ALLOWED_HOSTS)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not host_allowed(newurl):
            raise UpdateError(f"redirecionamento recusado: {urllib.parse.urlparse(newurl).hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, timeout: float = 20.0):
    if not host_allowed(url):
        raise UpdateError("endereço fora do GitHub (HTTPS) recusado")
    opener = urllib.request.build_opener(_SafeRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "KerbHUD-updater", "Accept": "application/vnd.github+json, */*"})
    try:
        return opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("repositório ou release não encontrado (o repositório é público e já tem um Release?)") from exc
        if exc.code in (403, 429):
            raise UpdateError("o GitHub recusou a consulta (limite de acessos); tente de novo em alguns minutos") from exc
        raise UpdateError(f"erro do GitHub: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(f"sem conexão com o GitHub: {getattr(exc, 'reason', exc)}") from exc


def http_json(url: str) -> dict:
    import json
    with _open(url) as r:
        data = r.read(2_000_000)
    try:
        return json.loads(data.decode("utf-8"))
    except ValueError as exc:
        raise UpdateError("resposta inesperada do GitHub") from exc


def http_download(url: str, dest: Path, progress: Optional[Callable[[int, int], None]] = None) -> None:
    with _open(url, timeout=30.0) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        if total > MAX_DOWNLOAD:
            raise UpdateError("arquivo grande demais para ser uma atualização")
        got = 0
        while chunk := r.read(256 * 1024):
            got += len(chunk)
            if got > MAX_DOWNLOAD:
                raise UpdateError("arquivo grande demais para ser uma atualização")
            f.write(chunk)
            if progress:
                progress(got, total)


def pick_asset(assets: list[dict], frozen: bool) -> Optional[dict]:
    """.exe: `*windows*.zip`; rodando pelo código-fonte: `*source*.zip`."""
    want = "windows" if frozen else "source"
    for a in assets:
        n = str(a.get("name", "")).lower()
        if n.endswith(".zip") and want in n:
            return a
    return None


def check_latest(repo: str, current: str, frozen: Optional[bool] = None,
                 fetch_json: Callable[[str], dict] = http_json) -> Optional[ReleaseInfo]:
    """Devolve o release mais novo, ou None se já está atualizado. Levanta UpdateError em falhas."""
    if not valid_repo(repo):
        raise UpdateError("repositório não configurado (Config → Configurações → Atualização: usuario/repositorio)")
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    data = fetch_json(API.format(repo=repo))
    if not isinstance(data, dict) or not data.get("tag_name"):
        raise UpdateError("o repositório ainda não tem nenhum Release publicado")
    try:
        if not is_newer(str(data["tag_name"]), current):
            return None
    except ValueError as exc:
        raise UpdateError(f"versão do release ilegível: {data['tag_name']!r}") from exc
    assets = [a for a in data.get("assets", []) if isinstance(a, dict)]
    asset = pick_asset(assets, frozen)
    if asset is None:
        kind = "Windows (.exe)" if frozen else "código-fonte"
        raise UpdateError(f"o release {data['tag_name']} não tem o arquivo zip de {kind}")
    sha = next((a for a in assets if a.get("name") == asset["name"] + ".sha256"), None)
    return ReleaseInfo(version=str(data["tag_name"]).lstrip("vV"), notes=str(data.get("body") or "")[:4000],
                       asset_name=str(asset["name"]), asset_url=str(asset.get("browser_download_url", "")),
                       sha256_url=str(sha.get("browser_download_url", "")) if sha else "",
                       size=int(asset.get("size") or 0))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path, expected_text: str) -> None:
    m = re.search(r"\b([0-9a-fA-F]{64})\b", expected_text)
    if not m:
        raise UpdateError("arquivo .sha256 do release ilegível")
    if sha256_of(path).lower() != m.group(1).lower():
        raise UpdateError("o arquivo baixado não confere com o SHA-256 do release (corrompido ou adulterado)")


def safe_extract(zip_path: Path, dest: Path) -> None:
    """Extrai recusando caminhos absolutos, `..`, links e zips gigantes."""
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise UpdateError("o arquivo baixado não é um zip válido") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_UNPACKED:
            raise UpdateError("zip grande demais")
        for i in infos:
            name = i.filename.replace("\\", "/")
            if name.startswith("/") or re.match(r"^[A-Za-z]:", name) or ".." in name.split("/"):
                raise UpdateError(f"zip com caminho perigoso recusado: {i.filename}")
            if (i.external_attr >> 16) & 0o170000 == 0o120000:
                raise UpdateError("zip com link simbólico recusado")
            target = (dest / name).resolve()
            if dest != target and dest not in target.parents:
                raise UpdateError(f"zip com caminho perigoso recusado: {i.filename}")
        zf.extractall(dest)


def content_root(extracted: Path) -> Path:
    """Zips do GitHub trazem uma pasta única por fora; desce nela."""
    items = [p for p in extracted.iterdir()]
    if len(items) == 1 and items[0].is_dir() and not (extracted / "src").exists() and not (extracted / "KerbHUD.exe").exists():
        return items[0]
    return extracted


def read_source_version(root: Path) -> str:
    init = root / "src" / "kerbhud" / "__init__.py"
    if not init.is_file():
        raise UpdateError("o zip não parece ser do KerbHUD (falta src/kerbhud)")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
    if not m:
        raise UpdateError("o zip não informa a versão")
    return m.group(1)


def apply_source_update(new_root: Path, app_root: Path, expect_version: str) -> list[str]:
    """Copia os arquivos novos por cima do programa (modo código-fonte). Devolve a lista de arquivos trocados.

    O que existia é guardado em `.backup/<versão antiga>/`. `dados/` e as demais pastas protegidas são ignoradas.
    """
    ver = read_source_version(new_root)
    if parse_version(ver) != parse_version(expect_version):
        raise UpdateError(f"o zip é da versão {ver}, não da {expect_version}")
    old = "antiga"
    try:
        old = read_source_version(app_root)
    except UpdateError:
        pass
    backup = app_root / ".backup" / old
    changed: list[str] = []
    for src in sorted(new_root.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(new_root)
        if rel.parts[0] in PROTECTED or "__pycache__" in rel.parts:
            continue
        dest = app_root / rel
        if dest.exists():
            if dest.read_bytes() == src.read_bytes():
                continue
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup / rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        changed.append(rel.as_posix())
    return changed


def write_swap_script(new_dir: Path, app_root: Path, exe_name: str, pid: int) -> Path:
    """(.exe) Gera o .bat que espera o programa fechar, copia os arquivos novos (sem tocar em `dados`) e reabre."""
    bat = app_root / "_update" / "aplicar-atualizacao.bat"
    bat.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "@echo off", "chcp 65001 >nul",
        ":espera", f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul', "if not errorlevel 1 (timeout /t 1 >nul & goto espera)",
        f'robocopy "{new_dir}" "{app_root}" /E /XD dados .backup _update /NFL /NDL /NJH /NJS /NP >nul',
        f'start "" "{app_root / exe_name}"',
        f'rmdir /S /Q "{app_root / "_update"}"',
    ]
    bat.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    return bat


def download_and_prepare(info: ReleaseInfo, work_dir: Path,
                         progress: Optional[Callable[[int, int], None]] = None,
                         download: Callable[..., None] = http_download,
                         fetch_text: Optional[Callable[[str], str]] = None) -> Path:
    """Baixa, confere e extrai. Devolve a pasta com o conteúdo novo (pronta para `apply_*`)."""
    if not info.asset_url:
        raise UpdateError("release sem endereço de download")
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    zpath = work_dir / info.asset_name.replace("/", "_").replace("\\", "_")
    download(info.asset_url, zpath, progress)
    if info.sha256_url:
        if fetch_text is None:
            def fetch_text(u: str) -> str:
                with _open(u) as r:
                    return r.read(4096).decode("utf-8", "replace")
        verify_sha256(zpath, fetch_text(info.sha256_url))
    out = work_dir / "novo"
    safe_extract(zpath, out)
    return content_root(out)
