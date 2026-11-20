"""Gera src/kerbhud/core/lmu_teams_data.py a partir de uma lista equipe->fabricante (JSON {veiculo: fabricante}).

Uso: python tools/gen_lmu_teams.py CAMINHO/brands.json
A lista de referência vem do TinyPedal (GPLv3). Aqui só os FATOS (equipe/número -> fabricante) são conferidos e
regravados; nenhum código ou imagem é copiado. Entradas "Custom Team" e fabricantes fora do catálogo ficam de fora.
"""
import json, re, sys
from pathlib import Path

M = {'Oreca': 'oreca', 'Ferrari': 'ferrari', 'Porsche': 'porsche', 'Aston Martin': 'astonmartin', 'BMW': 'bmw',
     'McLaren': 'mclaren', 'Cadillac': 'cadillac', 'Mercedes-AMG': 'mercedes', 'Peugeot': 'peugeot', 'Lexus': 'lexus',
     'Toyota': 'toyota', 'Corvette': 'corvette', 'Chevrolet Corvette': 'corvette', 'Ligier': 'ligier', 'Ford': 'ford',
     'Ford Mustang': 'ford', 'Alpine': 'alpine', 'Lamborghini': 'lamborghini', 'Vanwall': 'vanwall', 'ADESS': 'adess',
     'Glickenhaus': 'glickenhaus', 'Isotta Fraschini': 'isotta', 'Genesis': 'genesis', 'Duqueine': 'duqueine',
     'Ginetta': 'ginetta'}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).upper()


def main(src: str) -> None:
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    exact = {}
    for k, v in data.items():
        if v not in M or "CUSTOM TEAM" in k.upper() or ":" not in k:
            continue
        key = norm(k)
        exact[key] = M[v]
    out = ['"""Equipe do Le Mans Ultimate -> fabricante. GERADO por tools/gen_lmu_teams.py (não edite à mão;',
           'use o brand_overrides.json para ajustes seus). Chave = texto do veículo até o fim da série ("... #99:WEC")."""',
           "", "BY_ENTRY = {"]
    out += [f'    "{k}": "{v}",' for k, v in sorted(exact.items())]
    out += ["}", ""]
    Path(__file__).resolve().parents[1].joinpath("src/kerbhud/core/lmu_teams_data.py").write_text("\n".join(out), encoding="utf-8")
    print(len(exact), "entradas")


if __name__ == "__main__":
    main(sys.argv[1])
