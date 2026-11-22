"""Análise de sensibilidade do score comunicacional WorkSense
Uso, na pasta dos notebooks:
    python teste_sensibilidade_linguistica.py \
        --oficial ../Logs/indicadores_chat.json \
        --scores ../Logs/chat_scores.json

Não altera indicadores nem scores oficiais. Reproduz a lógica do notebook
calculosDeScore.ipynb para os parâmetros linguísticos testados.

As alternativas são verificações de sensibilidade, e não parâmetros
selecionados por desempenho contra os perfis simulados.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any

WEIGHT_SENTIMENT = 8.0 / 15.0
DEFAULTS = dict(
    length_min=2.0,
    sentence_min=0.25,
    lexical_min=0.08,
    fallback_ratio=0.20,
    mad_multiplier=1.4826,
    distance_divisor=3.0,
    length_weight=0.35,
    lexical_weight=0.45,
    sentence_weight=0.20,
)
USER_NAMES = {f"user-00{i}": p for i, p in enumerate("ABCD", 1)}


def load(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def get_period(day: str, control: bool) -> str | None:
    if control:
        if "2026-05-04" <= day <= "2026-05-15":
            return "referencia"
        if "2026-05-18" <= day <= "2026-05-29":
            return "controle"
        if "2026-06-01" <= day <= "2026-06-12":
            return "reanalise"
    else:
        if "2026-05-01" <= day <= "2026-05-30":
            return "baseline"
        if "2026-05-31" <= day <= "2026-06-14":
            return "reanalise"
    return None


def prepare(source: dict[str, Any], control: bool):
    blocks = {}
    for name in ("basicLinguistic", "sentimentAnalysis"):
        blocks[name] = {
            (user, item["date"]): item[name]
            for user, items in source[name].items()
            for item in items
        }
    lex = {
        (user, item["period"]): item
        for user, items in source["lexicalDiversityByPeriod"].items()
        for item in items
    }
    keys = sorted(set(blocks["basicLinguistic"]) | set(blocks["sentimentAnalysis"]))
    return [
        {
            "user": user,
            "date": day,
            "period": get_period(day, control),
            "basic": blocks["basicLinguistic"].get((user, day), {}),
            "sentiment": blocks["sentimentAnalysis"].get((user, day), {}),
            "lexical": lex.get((user, get_period(day, control)), {}),
        }
        for user, day in keys
    ]


def clamp(value):
    return max(0.0, min(float(value), 100.0))


def pattern(value, reference, min_scale, config, activation=None, label=None):
    if value is None or not isinstance(reference, dict):
        return None
    center = reference.get("median")
    if not isinstance(center, (int, float)):
        return None
    mad = reference.get("mad")
    scales = {
        "MAD": config["mad_multiplier"] * float(mad) if isinstance(mad, (int, float)) else 0,
        "minimo": min_scale,
        "proporcional": abs(float(center)) * config["fallback_ratio"],
    }
    winner = max(scales, key=scales.get)
    if activation is not None:
        activation[(label, winner)] += 1
    distance = abs(float(value) - float(center)) / max(scales.values())
    return clamp((1 - min(distance / config["distance_divisor"], 1)) * 100)


def lexical_pattern(value, baseline, config, activation=None):
    if not isinstance(value, (int, float)) or not isinstance(baseline, (int, float)):
        return None
    scales = {
        "minimo": config["lexical_min"],
        "proporcional": abs(float(baseline)) * config["fallback_ratio"],
    }
    winner = max(scales, key=scales.get)
    if activation is not None:
        activation[("MATTR", winner)] += 1
    distance = abs(float(value) - float(baseline)) / max(scales.values())
    return clamp((1 - min(distance / config["distance_divisor"], 1)) * 100)


def daily_score(item, config, activation=None):
    basic, sentiment, lexical = item["basic"], item["sentiment"], item["lexical"]
    refs = basic.get("baselineReference") or {}
    length = pattern(
        basic.get("avgWordsPerMessage"), refs.get("avgWordsPerMessage"),
        config["length_min"], config, activation, "comprimento",
    )
    sentences = pattern(
        basic.get("avgSentencesPerMessage"), refs.get("avgSentencesPerMessage"),
        config["sentence_min"], config, activation, "sentencas",
    )
    lexical_score = lexical_pattern(
        lexical.get("lexicalDiversityMattr"),
        lexical.get("baselineLexicalDiversityMattr"), config, activation,
    )
    weighted = [(length, config["length_weight"]),
                (lexical_score, config["lexical_weight"]),
                (sentences, config["sentence_weight"])]
    weight_available = sum(weight for value, weight in weighted if value is not None)
    linguistic = (sum(value * weight for value, weight in weighted if value is not None) / weight_available
                  if weight_available else None)
    pos, neg = sentiment.get("avgPositiveScore"), sentiment.get("avgNegativeScore")
    sentiment_score = clamp(50 + 50 * (pos - neg)) if pos is not None and neg is not None else None
    if linguistic is None and sentiment_score is None:
        score = None
    elif linguistic is None:
        score = sentiment_score
    elif sentiment_score is None:
        score = linguistic
    else:
        score = WEIGHT_SENTIMENT * sentiment_score + (1 - WEIGHT_SENTIMENT) * linguistic
    return round(score, 2) if score is not None else None


def compute(data, **changes):
    config = {**DEFAULTS, **changes}
    counters = Counter()
    rows = []
    for item in data:
        rows.append({
            "userId": item["user"],
            "date": item["date"],
            "period": item["period"],
            "score": daily_score(item, config, counters),
        })
    totals = defaultdict(lambda: [0.0, 0])
    for row in rows:
        if row["score"] is not None:
            t = totals[(row["userId"], row["period"])]
            t[0] += row["score"]
            t[1] += 1
    means = {key: value[0] / value[1] for key, value in totals.items()}
    return rows, means, counters


def deltas(means, control):
    return {
        USER_NAMES[user]: round(means[(user, "reanalise")] - means[(user, "controle" if control else "baseline")], 4)
        for user in USER_NAMES
    }


def reference_control(means):
    return {
        USER_NAMES[user]: round(means[(user, "controle")] - means[(user, "referencia")], 4)
        for user in USER_NAMES
    }


def configs():
    result = [("Atual", {})]
    result.extend((f"mín. comprimento={v:g}", {"length_min": v}) for v in [1, 3, 4, 5, 6])
    result.extend((f"mín. sentenças={v:g}", {"sentence_min": v}) for v in [.15, .35, .45, .55])
    result.extend((f"mín. MATTR={v:g}", {"lexical_min": v}) for v in [.04, .12, .16, .2])
    result.extend((f"escala proporcional={v:.0%}", {"fallback_ratio": v}) for v in [.10, .15, .25, .30])
    result.extend((f"divisor={v:g}", {"distance_divisor": v}) for v in [2, 2.5, 3.5, 4])
    result.extend((f"multiplicador MAD={v:g}", {"mad_multiplier": v}) for v in [1, 1.25, 1.75, 2])
    for w in [.30, .60]:
        other = 1 - w
        result.append((f"peso MATTR={w:.0%}", {
            "lexical_weight": w,
            "length_weight": other * .35 / .55,
            "sentence_weight": other * .20 / .55,
        }))
    return result


def fmt(v):
    return f"{v:+.2f}".replace(".", ",")


def markdown(result, validation):
    lines = [
        "# Sensibilidade da normalização linguística — WorkSense",
        "",
        "**Configuração oficial:** sentimento 8/15; interação linguística 7/15;",
        "pesos internos 35% comprimento, 45% MATTR e 20% sentenças.",
        "Somente um parâmetro é modificado de cada vez.",
        "",
        "As células com valores representam variações de médias de scores, em pontos.",
        "",
        "## Baseline oficial → reanálise",
        "",
        "| Cenário | A | B | C | D |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in result:
        lines.append("| " + row["scenario"] + " | " + " | ".join(fmt(row["oficial"][k]) for k in "ABCD") + " |")
    lines += ["", "## Controle → reanálise", "", "| Cenário | A | B | C | D |", "|---|---:|---:|---:|---:|",
              *["| " + row["scenario"] + " | " + " | ".join(fmt(row["controle"][k]) for k in "ABCD") + " |" for row in result],
              "", "## Referência → controle", "", "| Cenário | A | B | C | D |", "|---|---:|---:|---:|---:|",
              *["| " + row["scenario"] + " | " + " | ".join(fmt(row["referencia_controle"][k]) for k in "ABCD") + " |" for row in result],
              "", "## Verificação", "", validation, "",
              "A escala proporcional domina a escala baseada no MAD na configuração oficial deste conjunto de dados.",
              "Consequentemente, esses resultados não demonstram sensibilidade a ajustes pequenos do MAD.",
              "As comparações são exploratórias e não constituem validação externa ou seleção de parâmetros ótimos.", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--oficial", type=Path, default=Path("../Logs/indicadores_chat.json"))
    ap.add_argument("--scores", type=Path, default=None, help="arquivo opcional de scores oficiais para verificar reprodução")
    ap.add_argument("--saida", type=Path, default=Path("relatorio_sensibilidade_linguistica.md"))
    args = ap.parse_args()
    official = prepare(load(args.oficial), control=False)
    control = prepare(load(args.controle), control=True)
    baseline_rows, _, counts = compute(official)
    text_validation = f"Recalculados {len(baseline_rows)} dias da execução oficial."
    if args.scores is not None:
        original = load(args.scores)
        by_key = {(r["userId"], r["date"]):r["score"] for r in original}
        errors = [abs(r["score"] - by_key[(r["userId"], r["date"])]) for r in baseline_rows]
        text_validation += f" Maior diferença em relação ao JSON oficial: {max(errors):.4f} ponto."
    print(text_validation)
    print("Origem das escalas na configuração atual (120 registros):", dict(counts))
    results=[]
    for name, alterations in configs():
        _, off_means, _ = compute(official, **alterations)
        _, ctl_means, _ = compute(control, **alterations)
        results.append({
            "scenario":name,
            "parameters":alterations,
            "oficial":deltas(off_means,control=False),
            "controle":deltas(ctl_means,control=True),
            "referencia_controle":reference_control(ctl_means),
        })
    args.saida.write_text(markdown(results,text_validation),encoding="utf-8")
    print(f"Relatório salvo em: {args.saida}")
    print("Resumo (baseline → reanálise):")
    for row in results:
        if row["scenario"] in ("Atual","escala proporcional=10%","escala proporcional=15%","escala proporcional=25%","escala proporcional=30%","divisor=2","divisor=4","peso MATTR=30%","peso MATTR=60%"):
            print(row["scenario"],row["oficial"])

if __name__ == "__main__":
    main()
