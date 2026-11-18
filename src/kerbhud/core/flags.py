"""Bandeiras de países/regiões: de onde vem o país de cada piloto e como baixar as imagens.

* **iRacing:** o YAML de sessão traz o "flair" de cada piloto (`FlairName`, ex.: "Brazil"). Convertemos o
  nome em código ISO (`br`).
* **Le Mans Ultimate:** o jogo NÃO publica o país dos pilotos. Só dá para mostrar bandeira pelo que você
  informar em `settings.json`: `"my_country": "br"` (a sua) e `"driver_flags": {"Nome do Piloto": "pt"}`.
* As imagens (PNG) ficam em `<pasta de configuração>/flags/<codigo>.png` e vêm do FlagCDN
  (`flagcdn.com`, gratuito), por ação do usuário. Nada é baixado sem o usuário pedir.
"""
from __future__ import annotations

import os
import re
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Optional

from .model import CarState

FLAG_URL = "https://flagcdn.com/w80/{code}.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# "código nome1|nome2|..." (nomes em inglês, como o iRacing escreve; alguns apelidos comuns)
_TABLE = """
ad Andorra
ae United Arab Emirates|UAE
af Afghanistan
ag Antigua and Barbuda
al Albania
am Armenia
ao Angola
ar Argentina
at Austria
au Australia
aw Aruba
az Azerbaijan
ba Bosnia and Herzegovina|Bosnia
bb Barbados
bd Bangladesh
be Belgium
bf Burkina Faso
bg Bulgaria
bh Bahrain
bi Burundi
bj Benin
bm Bermuda
bn Brunei
bo Bolivia
br Brazil|Brasil
bs Bahamas
bt Bhutan
bw Botswana
by Belarus
bz Belize
ca Canada
cd Democratic Republic of the Congo|DR Congo
cg Republic of the Congo|Congo
ch Switzerland
ci Ivory Coast|Cote d'Ivoire
cl Chile
cm Cameroon
cn China
co Colombia
cr Costa Rica
cu Cuba
cv Cape Verde|Cabo Verde
cw Curacao
cy Cyprus
cz Czech Republic|Czechia
de Germany|Deutschland
dj Djibouti
dk Denmark
dm Dominica
do Dominican Republic
dz Algeria
ec Ecuador
ee Estonia
eg Egypt
er Eritrea
es Spain|Espana
et Ethiopia
fi Finland
fj Fiji
fo Faroe Islands
fr France
ga Gabon
gb United Kingdom|UK|Great Britain|Britain|United Kingdom of Great Britain and Northern Ireland
gb-eng England
gb-nir Northern Ireland
gb-sct Scotland
gb-wls Wales
gd Grenada
ge Georgia
gg Guernsey
gh Ghana
gi Gibraltar
gl Greenland
gm Gambia
gn Guinea
gq Equatorial Guinea
gr Greece
gt Guatemala
gu Guam
gw Guinea-Bissau
gy Guyana
hk Hong Kong
hn Honduras
hr Croatia
ht Haiti
hu Hungary
id Indonesia
ie Ireland
il Israel
im Isle of Man
in India
iq Iraq
ir Iran
is Iceland
it Italy
je Jersey
jm Jamaica
jo Jordan
jp Japan
ke Kenya
kg Kyrgyzstan
kh Cambodia
ki Kiribati
km Comoros
kn Saint Kitts and Nevis
kp North Korea
kr South Korea|Korea|Republic of Korea
kw Kuwait
ky Cayman Islands
kz Kazakhstan
la Laos
lb Lebanon
lc Saint Lucia
li Liechtenstein
lk Sri Lanka
lr Liberia
ls Lesotho
lt Lithuania
lu Luxembourg
lv Latvia
ly Libya
ma Morocco
mc Monaco
md Moldova
me Montenegro
mg Madagascar
mh Marshall Islands
mk North Macedonia|Macedonia
ml Mali
mm Myanmar|Burma
mn Mongolia
mo Macau|Macao
mr Mauritania
mt Malta
mu Mauritius
mv Maldives
mw Malawi
mx Mexico
my Malaysia
mz Mozambique
na Namibia
ne Niger
ng Nigeria
ni Nicaragua
nl Netherlands|The Netherlands|Holland
no Norway
np Nepal
nr Nauru
nz New Zealand
om Oman
pa Panama
pe Peru
pg Papua New Guinea
ph Philippines
pk Pakistan
pl Poland
pr Puerto Rico
ps Palestine
pt Portugal
pw Palau
py Paraguay
qa Qatar
ro Romania
rs Serbia
ru Russia|Russian Federation
rw Rwanda
sa Saudi Arabia
sb Solomon Islands
sc Seychelles
sd Sudan
se Sweden
sg Singapore
si Slovenia
sk Slovakia
sl Sierra Leone
sm San Marino
sn Senegal
so Somalia
sr Suriname
ss South Sudan
st Sao Tome and Principe
sv El Salvador
sy Syria
sz Eswatini|Swaziland
td Chad
tg Togo
th Thailand
tj Tajikistan
tl Timor-Leste|East Timor
tm Turkmenistan
tn Tunisia
to Tonga
tr Turkey|Turkiye
tt Trinidad and Tobago
tv Tuvalu
tw Taiwan
tz Tanzania
ua Ukraine
ug Uganda
us United States|United States of America|USA|America
uy Uruguay
uz Uzbekistan
va Vatican City|Vatican
vc Saint Vincent and the Grenadines
ve Venezuela
vn Vietnam|Viet Nam
vu Vanuatu
ws Samoa
xk Kosovo
ye Yemen
za South Africa
zm Zambia
zw Zimbabwe
"""


def _norm(text: str) -> str:
    """Minúsculas, sem acentos nem pontuação, espaços simples."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t.replace("'", ""))).strip()


_BY_NAME: dict[str, str] = {}
ALL_CODES: list[str] = []
for _line in _TABLE.strip().splitlines():
    _code, _names = _line.split(" ", 1)
    ALL_CODES.append(_code)
    _BY_NAME[_norm(_code)] = _code  # o próprio código também vale como entrada ("br", "gb-eng")
    for _n in _names.split("|"):
        _BY_NAME[_norm(_n)] = _code
_CODE_RE = re.compile(r"^[a-z]{2}(-[a-z]{3})?$")


def country_code(text: Optional[str]) -> Optional[str]:
    """Nome de país (inglês) ou código ISO -> código em minúsculas; None se não reconhecer (não chuta)."""
    if not text or not str(text).strip():
        return None
    code = _BY_NAME.get(_norm(text))
    if code:
        return code
    raw = str(text).strip().lower()
    return raw if raw in ALL_CODES else None


class FlagResolver:
    """Decide o país de cada carro: dado do simulador > `driver_flags` do usuário > `my_country`."""

    def __init__(self, settings: Optional[Mapping] = None):
        self.reload(settings)

    def reload(self, settings: Optional[Mapping] = None) -> None:
        """Relê `my_country` e `driver_flags` (usado quando a pessoa muda isso na janela de configurações)."""
        s = settings or {}
        self.mine = country_code(s.get("my_country"))
        raw = s.get("driver_flags") if isinstance(s.get("driver_flags"), dict) else {}
        self.by_driver = {_norm(k): c for k, v in raw.items() if (c := country_code(v))}

    def code_for(self, car: CarState) -> Optional[str]:
        if car.country:
            return car.country
        by_name = self.by_driver.get(_norm(car.driver_name))
        if by_name:
            return by_name
        return self.mine if car.is_player else None


# ---- download ----------------------------------------------------------- #
@dataclass
class FlagResult:
    downloaded: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: int = 0  # já existiam
    fatal: str = ""

    @property
    def summary(self) -> str:
        if self.fatal:
            return self.fatal
        parts = [f"{len(self.downloaded)} bandeiras baixadas"]
        if self.skipped:
            parts.append(f"{self.skipped} já existiam")
        if self.errors:
            parts.append(f"{len(self.errors)} falhas")
        return "; ".join(parts)


def http_fetch(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "KerbHUD-flag-fetch"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL https fixa)
        return resp.read()


def fetch_flags(dest: Path, fetch: Callable[[str], bytes] = http_fetch, codes: Optional[list[str]] = None,
                overwrite: bool = False, progress: Optional[Callable[[int, int], None]] = None) -> FlagResult:
    """Baixa as bandeiras (PNG de 80 px de largura) para `dest/<codigo>.png`."""
    res = FlagResult()
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    todo = list(codes or ALL_CODES)
    fails_in_a_row = 0
    for i, code in enumerate(todo, start=1):
        if progress:
            progress(i, len(todo))
        target = dest / f"{code}.png"
        if target.exists() and not overwrite:
            res.skipped += 1
            continue
        try:
            data = fetch(FLAG_URL.format(code=code))
            if not data.startswith(PNG_SIGNATURE):
                raise ValueError("arquivo não é PNG")
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, target)
            res.downloaded.append(code)
            fails_in_a_row = 0
        except Exception as exc:  # noqa: BLE001
            res.errors.append(f"{code}: {exc}")
            fails_in_a_row += 1
            if fails_in_a_row >= 5 and not res.downloaded:  # sem internet: não insiste 200 vezes
                res.fatal = f"Não foi possível baixar as bandeiras ({exc.__class__.__name__}). Verifique a internet."
                break
    return res


def installed_flags(directory: Path) -> list[str]:
    d = Path(directory)
    return sorted(p.stem for p in d.glob("*.png")) if d.is_dir() else []
