"""
Pasa las descargas del esquema viejo al de carpetas por semana:
  <curso>/archivos/S05_Práctica.pdf  →  <curso>/Semana 05/Práctica.pdf   (S00_ → General/)
  <curso>/videos/<grabación>.mp4     →  <curso>/Semana 05/<grabación>.mp4 (también .skip/.fail)
Solo mueve dentro del mismo disco (instantáneo). Si el destino ya existe con el mismo contenido,
la copia vieja sobra y se quita; si el contenido es distinto se conservan ambas.
"""

import filecmp
import re
from pathlib import Path

from scrape import carpeta_curso, carpeta_semana, semana_de_texto

_RE_PREFIJO = re.compile(r"^S(\d{2})_(.+)$")
_CARPETAS_VIEJAS = ("archivos", "videos")
_COMPARAR_HASTA = 50_000_000  # más grande (videos): basta el tamaño igual para darlo por idéntico


def hay_esquema_viejo(base_dir: str) -> bool:
    base = Path(base_dir).expanduser()
    return base.is_dir() and any(any(base.glob(f"*/*/{n}")) for n in _CARPETAS_VIEJAS)


def _mismo_contenido(a: Path, b: Path) -> bool:
    if a.stat().st_size != b.stat().st_size:
        return False
    return a.stat().st_size > _COMPARAR_HASTA or filecmp.cmp(a, b, shallow=False)


def _destino(f: Path, curso_dir: Path, semana_video: dict) -> Path:
    if f.parent.name == "archivos":
        m = _RE_PREFIJO.match(f.name)
        semana, nombre = (int(m.group(1)), m.group(2).strip()) if m else (0, f.name)
        return curso_dir / carpeta_semana(semana) / nombre
    # videos: la semana sale del listado (misma regla que scrape.grabaciones) o, si la grabación
    # ya no aparece en la API, del propio título ('( Semana 12 )')
    carpeta = semana_video.get((str(curso_dir).lower(), f.stem.lower()))
    return curso_dir / (carpeta or carpeta_semana(semana_de_texto(f.name))) / f.name


def _libre(ruta: Path) -> Path:
    """'X (otra versión).pdf' ya existe → 'X (otra versión) 2.pdf', 3, ..."""
    n = 2
    candidata = ruta
    while candidata.exists():
        candidata = ruta.with_name(f"{ruta.stem} {n}{ruta.suffix}")
        n += 1
    return candidata


def migrar(base_dir: str, cursos: list[dict], log=print, simular: bool = False) -> dict:
    """Mueve todo lo del esquema viejo. Con simular=True solo cuenta qué haría."""
    base = Path(base_dir).expanduser()
    semana_video = {}
    for c in cursos:
        for v in c["videos"]:
            carpeta, nombre = v["archivo"].split("/", 1)
            semana_video[(str(carpeta_curso(base_dir, c)).lower(), nombre.lower())] = carpeta

    r = {"movidos": 0, "duplicados": 0, "conservados_ambos": 0, "bloqueados": 0}
    viejas = [d for n in _CARPETAS_VIEJAS for d in base.glob(f"*/*/{n}") if d.is_dir()]
    for vieja in viejas:
        for f in sorted(p for p in vieja.iterdir() if p.is_file()):
            # un archivo abierto en otro programa (PermissionError) no frena los demás:
            # se queda donde está y se reintenta en la próxima detección
            try:
                destino = _destino(f, vieja.parent, semana_video)
                if destino.exists():
                    if _mismo_contenido(f, destino):
                        r["duplicados"] += 1
                        if not simular:
                            f.unlink()
                        continue
                    destino = _libre(destino.with_name(f"{destino.stem} (otra versión){destino.suffix}"))
                    r["conservados_ambos"] += 1
                if not simular:
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    f.rename(destino)
                r["movidos"] += 1
            except OSError as e:
                r["bloqueados"] += 1
                log("WARN", "#f59e0b", f"No se pudo mover {f.name}: {e.strerror or e}")
        try:
            if not simular and not any(vieja.iterdir()):
                vieja.rmdir()
        except OSError:
            pass

    accion = "Se moverían" if simular else "Movidos"
    log(
        "SUCCESS",
        "#22c55e",
        f"Carpetas por semana: {accion} {r['movidos']} archivo(s)"
        + (f", {r['duplicados']} copia(s) idéntica(s) quitada(s)" if r["duplicados"] else "")
        + (
            f", {r['conservados_ambos']} con dos versiones distintas (se guardan ambas)"
            if r["conservados_ambos"]
            else ""
        )
        + (f", {r['bloqueados']} en uso por otro programa (se reintenta luego)" if r["bloqueados"] else ""),
    )
    return r
