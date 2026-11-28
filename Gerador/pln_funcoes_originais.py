# Extração literal das células 2, 5, 8 e função group_by_user da célula 10 do notebook corrigido (correção 10).
# Importação carrega os mesmos modelos; nenhum I/O de arquivos experimentais.
import spacy
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

nlp = spacy.load("pt_core_news_sm")
APP_TIMEZONE = ZoneInfo("America/Sao_Paulo")
MATTR_WINDOW_SIZE = 20
MATTR_BLOCK_DAYS = 5

PERIOD_WINDOWS = {
    "baseline": ("2026-05-01", "2026-05-30"),
    "reanalise": ("2026-05-31", "2026-06-14"),
}
BASELINE_PERIOD_NAME = "baseline"
BASELINE_START_DATE, BASELINE_END_DATE = PERIOD_WINDOWS[BASELINE_PERIOD_NAME]


def normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def parse_message_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=APP_TIMEZONE)
    return parsed.astimezone(APP_TIMEZONE)


def get_date(created_at: str) -> str:
    return parse_message_datetime(created_at).date().isoformat()


def is_valid_word(token) -> bool:
    return (
        not token.is_space
        and not token.is_punct
        and not token.like_url
        and not token.like_email
    )


def get_words(doc):
    return [token for token in doc if is_valid_word(token)]


def get_lemmas(words):
    return [
        token.lemma_.lower()
        for token in words
        if not token.is_stop and token.lemma_.strip()
    ]


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def calculate_mattr(lemmas: list[str], window_size: int = MATTR_WINDOW_SIZE) -> float | None:
    """Calcula Moving-Average Type-Token Ratio (MATTR) em janelas lexicais fixas."""
    if window_size <= 0:
        raise ValueError("window_size deve ser maior que zero.")
    if len(lemmas) < window_size:
        return None

    window_ttrs = [
        len(set(lemmas[start:start + window_size])) / window_size
        for start in range(len(lemmas) - window_size + 1)
    ]
    return round(sum(window_ttrs) / len(window_ttrs), 4)


def _period_name_for_date(day: str, period_windows: dict[str, tuple[str, str]]) -> str | None:
    for period_name, (start_date, end_date) in period_windows.items():
        if start_date <= day <= end_date:
            return period_name
    return None


def extract_text_metrics(message_id: str, user_id: str, text: str) -> dict[str, Any]:
    text = normalize_text(text)
    doc = nlp(text)
    words = get_words(doc)
    lemmas = get_lemmas(words)

    pos_counter = Counter(token.pos_ for token in words)
    lemma_counter = Counter(lemmas)
    word_count = len(words)
    lemma_count = len(lemmas)

    return {
        "messageId": message_id,
        "userId": user_id,
        "text": text,
        "metrics": {
            "basicLinguistic": {
                "charCount": len(text),
                "tokenCount": len(doc),
                "wordCount": word_count,
                "sentenceCount": len(list(doc.sents)),
                "avgTokenLength": safe_divide(
                    sum(len(token.text) for token in words),
                    word_count,
                ),
                "lemmaCount": lemma_count,
                "uniqueLemmaCount": len(set(lemmas)),
                "stopwordCount": sum(1 for token in words if token.is_stop),
                "nounCount": pos_counter.get("NOUN", 0),
                "properNounCount": pos_counter.get("PROPN", 0),
                "verbCount": pos_counter.get("VERB", 0),
                "auxVerbCount": pos_counter.get("AUX", 0),
                "adjectiveCount": pos_counter.get("ADJ", 0),
                "adverbCount": pos_counter.get("ADV", 0),
                "pronounCount": pos_counter.get("PRON", 0),
                "topLemmas": dict(lemma_counter.most_common(10)),
            }
        },
    }


def extract_many_text_metrics(messages: list[dict]) -> list[dict]:
    return [
        extract_text_metrics(
            message_id=message["messageId"],
            user_id=message["userId"],
            text=message["text"],
        ) | {"createdAt": message["createdAt"]}
        for message in messages
    ]


def aggregate_by_day(results: list[dict]) -> list[dict]:
    grouped = defaultdict(list)

    for item in results:
        grouped[(item["userId"], get_date(item["createdAt"]))].append(item)

    daily_results = []

    for (user_id, day), items in grouped.items():
        metrics = [item["metrics"] for item in items]
        message_count = len(items)
        total_words = sum(m["basicLinguistic"]["wordCount"] for m in metrics)
        total_chars = sum(m["basicLinguistic"]["charCount"] for m in metrics)
        total_sentences = sum(m["basicLinguistic"]["sentenceCount"] for m in metrics)
        total_lemmas = sum(m["basicLinguistic"]["lemmaCount"] for m in metrics)

        # Diversidade lexical é calculada por bloco de dias com mensagens.
        daily_results.append({
            "userId": user_id,
            "date": day,
            "basicLinguistic": {
                "messageCount": message_count,
                "totalWords": total_words,
                "totalChars": total_chars,
                "totalSentences": total_sentences,
                "totalLemmas": total_lemmas,
                "avgWordsPerMessage": round(total_words / message_count, 2) if message_count else None,
                "avgCharsPerMessage": round(total_chars / message_count, 2) if message_count else None,
                "avgSentencesPerMessage": round(total_sentences / message_count, 2) if message_count else None,
                "totalNouns": sum(m["basicLinguistic"]["nounCount"] for m in metrics),
                "totalVerbs": sum(m["basicLinguistic"]["verbCount"] for m in metrics),
                "totalAdjectives": sum(m["basicLinguistic"]["adjectiveCount"] for m in metrics),
                "totalAdverbs": sum(m["basicLinguistic"]["adverbCount"] for m in metrics),
            },
        })

    return sorted(daily_results, key=lambda item: (item["userId"], item["date"]))


def _lexical_corpus_metrics(items: list[dict], window_size: int) -> dict:
    # Preserve a tokenização/lematização do corpus da implementação anterior.
    ordered = sorted(items, key=lambda item: parse_message_datetime(item["createdAt"]))
    text = " ".join(item["text"] for item in ordered)
    lemmas = get_lemmas(get_words(nlp(text))) if ordered else []
    return {
        "lexicalDiversityMattr": calculate_mattr(lemmas, window_size),
        "totalLemmas": len(lemmas),
        "mattrWindowCount": max(len(lemmas) - window_size + 1, 0),
    }


def aggregate_lexical_diversity_by_period(
    results: list[dict],
    period_windows: dict[str, tuple[str, str]],
    window_size: int = MATTR_WINDOW_SIZE,
    baseline_period_name: str = BASELINE_PERIOD_NAME,
    block_days: int = MATTR_BLOCK_DAYS,
) -> list[dict]:
    """MATTR retrospectiva por bloco de dias com mensagens, sem autorreferência.

    No baseline, a referência exclui todo o bloco avaliado. Nos demais
    períodos, a referência usa somente o baseline completo. Blocos finais
    menores são mantidos e explicitamente identificados.
    """
    if block_days <= 0 or window_size <= 0:
        raise ValueError("block_days e window_size devem ser positivos.")
    if baseline_period_name not in period_windows:
        raise ValueError("Período de referência inexistente.")
    grouped = defaultdict(lambda: defaultdict(list))
    for item in results:
        day = get_date(item["createdAt"])
        period = _period_name_for_date(day, period_windows)
        if period is not None:
            grouped[(item["userId"], period)][day].append(item)

    output = []
    for (user_id, period), items_by_day in grouped.items():
        baseline = grouped.get((user_id, baseline_period_name), {})
        days = sorted(items_by_day)
        for offset in range(0, len(days), block_days):
            block = days[offset:offset + block_days]
            block_set = set(block)
            reference_days = sorted(day for day in baseline
                if period != baseline_period_name or day not in block_set)
            observed = _lexical_corpus_metrics(
                [item for day in block for item in items_by_day[day]], window_size)
            reference = _lexical_corpus_metrics(
                [item for day in reference_days for item in baseline[day]], window_size)
            output.append({
                "userId": user_id,
                "period": period,
                "startDate": block[0],
                "endDate": block[-1],
                "dates": block,
                "blockDays": len(block),
                "referenceDates": reference_days,
                "referenceSampleDays": len(reference_days),
                **observed,
                "mattrWindowSize": window_size,
                "sampleSufficient": observed["lexicalDiversityMattr"] is not None,
                "baselineLexicalDiversityMattr": reference["lexicalDiversityMattr"],
                "referenceTotalLemmas": reference["totalLemmas"],
            })
    return sorted(output, key=lambda item: (item["userId"], item["startDate"]))


def _median_and_mad(values: list[float]) -> dict[str, float | int | None]:
    """Referência robusta do baseline: mediana e MAD (median absolute deviation)."""
    valid = [float(value) for value in values if isinstance(value, (int, float))]
    if not valid:
        return {"median": None, "mad": None, "sampleDays": 0}

    center = median(valid)
    mad = median([abs(value - center) for value in valid])

    return {
        "median": round(center, 4),
        "mad": round(mad, 4),
        "sampleDays": len(valid),
    }


def add_linguistic_baseline_reference(
    daily_results: list[dict],
    baseline_start_date: str,
    baseline_end_date: str,
) -> list[dict]:
    """
    Anexa a cada dia a referência linguística do próprio usuário no baseline.

    As medidas linguísticas deixam de ser avaliadas por faixas universais de
    "bom/ruim" e passam a indicar estabilidade ou desvio do padrão individual.
    """
    grouped = defaultdict(list)
    for item in daily_results:
        grouped[item["userId"]].append(item)

    enriched = []
    for user_id, items in grouped.items():
        baseline_items = [item for item in items
            if baseline_start_date <= item["date"] <= baseline_end_date]
        for item in items:
            # Leave-one-day-out no baseline; baseline completo na reanálise.
            reference_items = [ref["basicLinguistic"] for ref in baseline_items
                if ref["date"] != item["date"]]
            references = {
                key: _median_and_mad([ref.get(key) for ref in reference_items])
                for key in ("avgWordsPerMessage", "avgSentencesPerMessage")
            }
            enriched.append({
                **item,
                "basicLinguistic": {
                    **item["basicLinguistic"],
                    "baselineReference": references,
                },
            })

    return sorted(enriched, key=lambda item: (item["userId"], item["date"]))



from pysentimiento import create_analyzer
from collections import Counter, defaultdict
import os

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

sentiment_analyzer = create_analyzer(task="sentiment", lang="pt")

def extract_sentiment_metrics(message_id: str, user_id: str, text: str) -> dict:
    result = sentiment_analyzer.predict(text)

    return {
        "messageId": message_id,
        "userId": user_id,
        "text": text,
        "metrics": {
            "sentimentAnalysis": {
                "sentimentLabel": result.output,
                "positiveScore": round(result.probas.get("POS", 0.0), 4),
                "negativeScore": round(result.probas.get("NEG", 0.0), 4),
                "neutralScore": round(result.probas.get("NEU", 0.0), 4),
                "sentimentProbabilities": {
                    label: round(score, 4)
                    for label, score in result.probas.items()
                }
            }
        }
    }

def extract_many_sentiment_metrics(messages: list[dict]) -> list[dict]:
    return [
        extract_sentiment_metrics(
            message_id=message["messageId"],
            user_id=message["userId"],
            text=message["text"]
        ) | {
            "createdAt": message["createdAt"]
        }
        for message in messages
    ]

def get_dominant_sentiment(label_counter: Counter) -> str:
    if not label_counter:
        return "UNKNOWN"

    most_common = label_counter.most_common()
    highest_count = most_common[0][1]

    top_labels = [
        label
        for label, count in most_common
        if count == highest_count
    ]

    if len(top_labels) > 1:
        return "MIXED"

    return top_labels[0]

def aggregate_sentiment_by_day(results: list[dict]) -> list[dict]:
    grouped = defaultdict(list)

    for item in results:
        day = get_date(item["createdAt"])
        grouped[(item["userId"], day)].append(item)

    daily_results = []

    for (user_id, day), items in grouped.items():
        metrics = [
            item["metrics"]["sentimentAnalysis"]
            for item in items
        ]

        message_count = len(items)

        labels = [
            m["sentimentLabel"]
            for m in metrics
        ]

        label_counter = Counter(labels)

        avg_positive = sum(m["positiveScore"] for m in metrics) / message_count
        avg_negative = sum(m["negativeScore"] for m in metrics) / message_count
        avg_neutral = sum(m["neutralScore"] for m in metrics) / message_count

        daily_results.append({
            "userId": user_id,
            "date": day,
            "sentimentAnalysis": {
                "messageCount": message_count,
                "avgPositiveScore": round(avg_positive, 4),
                "avgNegativeScore": round(avg_negative, 4),
                "avgNeutralScore": round(avg_neutral, 4),
                "sentimentLabelCounts": dict(label_counter),
                "dominantSentiment": get_dominant_sentiment(label_counter)
            }
        })

    return daily_results


from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
from typing import Any
import numpy as np

semantic_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def extract_semantic_metrics(message_id: str, user_id: str, text: str) -> dict[str, Any]:
    embedding = semantic_model.encode(text)

    return {
        "messageId": message_id,
        "userId": user_id,
        "text": text,
        "metrics": {
            "semanticRepresentation": {
                "embedding": embedding.tolist(),
                "embeddingSize": len(embedding),
            }
        },
    }


def extract_many_semantic_metrics(messages: list[dict]) -> list[dict]:
    return [
        extract_semantic_metrics(
            message_id=message["messageId"],
            user_id=message["userId"],
            text=message["text"],
        ) | {"createdAt": message["createdAt"]}
        for message in messages
    ]


def group_texts_by_day(messages: list[dict]) -> list[dict]:
    grouped = defaultdict(list)

    for message in messages:
        grouped[(message["userId"], get_date(message["createdAt"]))].append(message["text"])

    return [
        {
            "userId": user_id,
            "date": day,
            "texts": texts,
            "text": " ".join(texts),
        }
        for (user_id, day), texts in grouped.items()
    ]


def extract_daily_semantic_embeddings(messages: list[dict]) -> list[dict]:
    results = []

    for item in group_texts_by_day(messages):
        embeddings = semantic_model.encode(
            item["texts"],
            normalize_embeddings=True,
        )

        embedding = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(embedding)

        if norm > 0:
            embedding = embedding / norm

        results.append({
            "userId": item["userId"],
            "date": item["date"],
            "text": item["text"],
            "semanticRepresentation": {
                "embedding": embedding.tolist(),
                "embeddingSize": len(embedding),
            },
        })

    return results


def classify_semantic_shift(distance: float | None) -> str:
    if distance is None:
        return "NO_PREVIOUS_OBSERVATION"
    if distance >= 0.50:
        return "HIGH"
    if distance >= 0.35:
        return "MODERATE"
    return "LOW"


def _cosine_similarity(first: np.ndarray, second: np.ndarray) -> float:
    similarity = cosine_similarity(
        first.reshape(1, -1),
        second.reshape(1, -1),
    )[0][0]
    return round(float(similarity), 4)


def calculate_semantic_shift(
    daily_results: list[dict],
    baseline_start_date: str | None = None,
    baseline_end_date: str | None = None,
) -> list[dict]:
    """
    Produz duas referências distintas:
    1) similaridade com a observação anterior (estabilidade local);
    2) similaridade com o centróide semântico do baseline (desvio de patamar).
    """
    grouped = defaultdict(list)
    for item in daily_results:
        grouped[item["userId"]].append(item)

    shift_results = []

    for user_id, items in grouped.items():
        items = sorted(items, key=lambda item: item["date"])

        baseline_items = [
            item
            for item in items
            if (baseline_start_date is None or item["date"] >= baseline_start_date)
            and (baseline_end_date is None or item["date"] <= baseline_end_date)
        ]

        baseline_centroid = None
        if baseline_items:
            baseline_embeddings = np.array([
                item["semanticRepresentation"]["embedding"]
                for item in baseline_items
            ])
            baseline_centroid = baseline_embeddings.mean(axis=0)

        for index, current_item in enumerate(items):
            current_embedding = np.array(
                current_item["semanticRepresentation"]["embedding"]
            )

            previous_date = None
            similarity_previous = None
            distance_previous = None

            if index > 0:
                previous_item = items[index - 1]
                previous_embedding = np.array(
                    previous_item["semanticRepresentation"]["embedding"]
                )
                previous_date = previous_item["date"]
                similarity_previous = _cosine_similarity(current_embedding, previous_embedding)
                distance_previous = round(1.0 - similarity_previous, 4)

            similarity_baseline = None
            distance_baseline = None
            if baseline_centroid is not None:
                similarity_baseline = _cosine_similarity(current_embedding, baseline_centroid)
                distance_baseline = round(1.0 - similarity_baseline, 4)

            shift_results.append({
                "userId": user_id,
                "date": current_item["date"],
                "semanticShift": {
                    "previousDate": previous_date,
                    "similarityToPreviousDay": similarity_previous,
                    "distanceToPreviousDay": distance_previous,
                    "semanticPreviousDayChangeLevel": classify_semantic_shift(distance_previous),
                    "similarityToBaseline": similarity_baseline,
                    "distanceToBaseline": distance_baseline,
                    "semanticBaselineChangeLevel": classify_semantic_shift(distance_baseline),
                },
            })

    return sorted(shift_results, key=lambda item: (item["userId"], item["date"]))



def group_by_user(results: list[dict]) -> dict:
    grouped = defaultdict(list)

    for item in results:
        user_id = item["userId"]

        item_without_user = {
            key: value
            for key, value in item.items()
            if key != "userId"
        }

        grouped[user_id].append(item_without_user)

    return dict(grouped)
