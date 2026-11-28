# Funções extraídas dos notebooks existentes; sem execução de I/O.
from __future__ import annotations


import json


from pathlib import Path


from dataclasses import asdict, dataclass


from typing import Any


@dataclass
class ScoreResult:
    userId: str
    date: str
    score: float | None
    components: dict[str, float | None]
    evidenceCoverage: float
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clamp(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    return max(min_value, min(value, max_value))


def round_score(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def safe_div(numerator: float, denominator: float, default: float | None = None) -> float | None:
    if denominator == 0:
        return default
    return numerator / denominator


def linear_score(
    value: float | None,
    min_value: float,
    max_value: float,
    invert: bool = False,
) -> float | None:
    if value is None or max_value == min_value:
        return None

    normalized = clamp((value - min_value) / (max_value - min_value), 0.0, 1.0)
    if invert:
        normalized = 1.0 - normalized
    return clamp(normalized * 100.0)


def weighted_score(
    components: dict[str, tuple[float | None, float]],
) -> tuple[float | None, float]:
    """
    Média ponderada apenas entre componentes efetivamente calculáveis.

    O segundo retorno representa a cobertura estrutural dos componentes disponíveis,
    não confiança estatística.
    """
    total_expected_weight = sum(weight for _, weight in components.values())
    available_weight = sum(
        weight
        for value, weight in components.values()
        if value is not None
    )

    if total_expected_weight <= 0 or available_weight <= 0:
        return None, 0.0

    score = sum(
        value * (weight / available_weight)
        for value, weight in components.values()
        if value is not None
    )
    coverage = available_weight / total_expected_weight
    return clamp(score), clamp(coverage, 0.0, 1.0)


def weighted_score_with_evidence(
    components: dict[str, tuple[float | None, float, float]],
) -> tuple[float | None, float]:
    """
    Calcula o score com os pesos definidos e mede a evidência separadamente.

    Diferentemente da versão anterior, menor evidência não altera silenciosamente o peso
    de um componente que já pôde ser calculado. Ela reduz somente evidenceCoverage.
    """
    score, _ = weighted_score({
        name: (value, weight)
        for name, (value, weight, _) in components.items()
    })

    total_expected_weight = sum(
        weight
        for _, weight, _ in components.values()
    )

    if total_expected_weight <= 0:
        return score, 0.0

    evidence_weight = sum(
        weight * clamp(evidence, 0.0, 1.0)
        for value, weight, evidence in components.values()
        if value is not None
    )

    return score, clamp(evidence_weight / total_expected_weight, 0.0, 1.0)


def baseline_pattern_score(
    value: float | None,
    reference: dict[str, Any] | None,
    minimum_scale: float,
) -> float | None:
    """
    Converte o desvio em relação ao baseline individual em 0..100.

    Usa mediana + MAD como referência robusta. O score chega a zero quando o desvio
    alcança aproximadamente três escalas robustas. `minimum_scale` evita explosão do
    desvio quando o baseline é praticamente constante.
    """
    if value is None or not reference:
        return None

    center = reference.get("median")
    mad = reference.get("mad")

    if not isinstance(center, (int, float)):
        return None

    robust_scale = (
        1.4826 * float(mad)
        if isinstance(mad, (int, float))
        else 0.0
    )
    fallback_scale = max(
        minimum_scale,
        abs(float(center)) * 0.20,
    )
    scale = max(robust_scale, fallback_scale)

    distance = abs(float(value) - float(center)) / scale
    return clamp((1.0 - min(distance / 3.0, 1.0)) * 100.0)


def baseline_value_pattern_score(
    value: float | None,
    baseline_value: float | None,
    minimum_scale: float,
) -> float | None:
    """Compara uma medida agregada do ciclo com o valor do próprio baseline."""
    if not isinstance(value, (int, float)) or not isinstance(baseline_value, (int, float)):
        return None

    fallback_scale = max(
        minimum_scale,
        abs(float(baseline_value)) * 0.20,
    )
    distance = abs(float(value) - float(baseline_value)) / fallback_scale
    return clamp((1.0 - min(distance / 3.0, 1.0)) * 100.0)


def calculate_sentiment_score(
    sentiment_data: dict[str, Any],
) -> tuple[float | None, dict[str, float | None], float]:
    avg_positive = sentiment_data.get("avgPositiveScore")
    avg_negative = sentiment_data.get("avgNegativeScore")

    if avg_positive is None or avg_negative is None:
        return None, {
            "sentimentValenceScore": None,
            "negativeSafetyScore": None,
        }, 0.0

    # NEG já participa da valência. negativeSafetyScore permanece apenas diagnóstico.
    sentiment_valence_score = clamp(
        50.0 + 50.0 * (avg_positive - avg_negative)
    )
    negative_safety_score = clamp(
        100.0 * (1.0 - avg_negative)
    )

    return sentiment_valence_score, {
        "sentimentValenceScore": round_score(sentiment_valence_score),
        "negativeSafetyScore": round_score(negative_safety_score),
    }, 1.0


def calculate_linguistic_interaction_score(
    linguistic_data: dict[str, Any],
    lexical_period_data: dict[str, Any] | None = None,
) -> tuple[float | None, dict[str, float | None], float, list[str]]:
    """
    Mede estabilidade do padrão linguístico individual, não "qualidade da escrita".

    Tamanho e estrutura das mensagens continuam sendo observados diariamente contra o
    baseline individual. A diversidade lexical usa MATTR calculado no corpus agregado
    do bloco; portanto, seu componente é constante entre os dias do mesmo bloco.
    """
    warnings: list[str] = []
    lexical_period_data = lexical_period_data or {}

    message_count = linguistic_data.get("messageCount")
    total_words = linguistic_data.get("totalWords")
    total_lemmas = linguistic_data.get("totalLemmas")
    avg_words_per_message = linguistic_data.get("avgWordsPerMessage")
    avg_sentences_per_message = linguistic_data.get("avgSentencesPerMessage")
    baseline_reference = linguistic_data.get("baselineReference", {})

    lexical_mattr = lexical_period_data.get("lexicalDiversityMattr")
    baseline_lexical_mattr = lexical_period_data.get("baselineLexicalDiversityMattr")
    lexical_sample_sufficient = lexical_period_data.get("sampleSufficient") is True

    message_evidence_score = None
    if message_count is not None:
        message_evidence_score = clamp((message_count / 2.0) * 100.0)

    message_length_pattern_score = baseline_pattern_score(
        avg_words_per_message,
        baseline_reference.get("avgWordsPerMessage"),
        minimum_scale=2.0,
    )
    sentence_pattern_score = baseline_pattern_score(
        avg_sentences_per_message,
        baseline_reference.get("avgSentencesPerMessage"),
        minimum_scale=0.25,
    )
    lexical_diversity_pattern_score = baseline_value_pattern_score(
        lexical_mattr,
        baseline_lexical_mattr,
        minimum_scale=0.08,
    )

    if lexical_diversity_pattern_score is None:
        window_size = lexical_period_data.get("mattrWindowSize")
        if lexical_period_data and not lexical_sample_sufficient:
            warnings.append(
                f"MATTR não utilizado porque o bloco possui menos de {window_size} lemas válidos."
            )
        else:
            warnings.append(
                "MATTR não utilizado porque não há diversidade lexical agregada do bloco ou referência do baseline."
            )

    linguistic_score, _ = weighted_score({
        "messageLengthPatternScore": (message_length_pattern_score, 0.35),
        "lexicalDiversityMattrPatternScore": (lexical_diversity_pattern_score, 0.45),
        "sentencePatternScore": (sentence_pattern_score, 0.20),
    })

    # O volume diário mede evidência para os padrões diários de tamanho/estrutura.
    # O componente lexical usa a suficiência do corpus do bloco, não o volume daquele dia.
    daily_sample_coverage = 0.0
    if total_words is not None:
        daily_sample_coverage = min(total_words / 30.0, 1.0)
    elif total_lemmas is not None:
        daily_sample_coverage = min(total_lemmas / 15.0, 1.0)

    lexical_evidence = (
        1.0
        if lexical_diversity_pattern_score is not None and lexical_sample_sufficient
        else 0.0
    )

    evidence_coverage = (
        (0.35 * daily_sample_coverage if message_length_pattern_score is not None else 0.0)
        + (0.45 * lexical_evidence if lexical_diversity_pattern_score is not None else 0.0)
        + (0.20 * daily_sample_coverage if sentence_pattern_score is not None else 0.0)
    )

    return linguistic_score, {
        "messageEvidenceScore": round_score(message_evidence_score),
        "messageLengthPatternScore": round_score(message_length_pattern_score),
        "lexicalDiversityMattrPatternScore": round_score(lexical_diversity_pattern_score),
        "sentencePatternScore": round_score(sentence_pattern_score),
    }, clamp(evidence_coverage, 0.0, 1.0), warnings


def calculate_semantic_score(
    semantic_data: dict[str, Any],
) -> tuple[float | None, dict[str, float | None], float]:
    similarity_previous = semantic_data.get("similarityToPreviousDay")
    similarity_baseline = semantic_data.get("similarityToBaseline")

    local_stability_score = (
        clamp(similarity_previous * 100.0)
        if similarity_previous is not None
        else None
    )
    baseline_consistency_score = (
        clamp(similarity_baseline * 100.0)
        if similarity_baseline is not None
        else None
    )

    # Baseline mede mudança de patamar; comparação anterior mede volatilidade local.
    semantic_score, coverage = weighted_score({
        "semanticBaselineConsistencyScore": (
            baseline_consistency_score,
            0.60,
        ),
        "semanticLocalStabilityScore": (
            local_stability_score,
            0.40,
        ),
    })

    return semantic_score, {
        "semanticBaselineConsistencyScore": round_score(
            baseline_consistency_score
        ),
        "semanticLocalStabilityScore": round_score(
            local_stability_score
        ),
    }, coverage


CHAT_SCORE_WEIGHTS = {
    "sentimentScore": 8.0 / 15.0,
    "linguisticInteractionScore": 7.0 / 15.0,
}


def calculate_chat_score(
    basic_linguistic_data: dict[str, Any] | None,
    sentiment_analysis_data: dict[str, Any] | None,
    semantic_shift_data: dict[str, Any] | None,
    lexical_diversity_period_data: dict[str, Any] | None = None,
) -> ScoreResult:
    warnings: list[str] = []

    basic_linguistic_data = basic_linguistic_data or {}
    sentiment_analysis_data = sentiment_analysis_data or {}
    semantic_shift_data = semantic_shift_data or {}

    user_id = (
        basic_linguistic_data.get("userId")
        or sentiment_analysis_data.get("userId")
        or semantic_shift_data.get("userId")
        or ""
    )
    date = (
        basic_linguistic_data.get("date")
        or sentiment_analysis_data.get("date")
        or semantic_shift_data.get("date")
        or ""
    )

    sentiment_score, sentiment_components, sentiment_evidence = (
        calculate_sentiment_score(
            sentiment_analysis_data.get("sentimentAnalysis", {})
        )
    )
    (
        linguistic_score,
        linguistic_components,
        linguistic_evidence,
        linguistic_warnings,
    ) = calculate_linguistic_interaction_score(
        basic_linguistic_data.get("basicLinguistic", {}),
        lexical_period_data=lexical_diversity_period_data,
    )
    semantic_score, semantic_components, semantic_evidence = (
        calculate_semantic_score(
            semantic_shift_data.get("semanticShift", {})
        )
    )

    warnings.extend(linguistic_warnings)

    if sentiment_score is None:
        warnings.append(
            "SentimentScore não calculado por falta de dados de sentimento."
        )
    if linguistic_score is None:
        warnings.append(
            "LinguisticInteractionScore não calculado por falta de dados linguísticos."
        )
    # A semântica permanece diagnóstica. Sua indisponibilidade não gera um aviso
    # de insuficiência de evidência para o score comunicacional.

    chat_score, evidence_coverage = weighted_score_with_evidence({
        "sentimentScore": (
            sentiment_score,
            CHAT_SCORE_WEIGHTS["sentimentScore"],
            sentiment_evidence,
        ),
        "linguisticInteractionScore": (
            linguistic_score,
            CHAT_SCORE_WEIGHTS["linguisticInteractionScore"],
            linguistic_evidence,
        ),
    })

    return ScoreResult(
        userId=user_id,
        date=date,
        score=round_score(chat_score),
        components={
            "sentimentScore": round_score(sentiment_score),
            "linguisticInteractionScore": round_score(linguistic_score),
            # Mantido exclusivamente para análise exploratória (sem peso no total).
            "semanticScore": round_score(semantic_score),
            **sentiment_components,
            **linguistic_components,
            **semantic_components,
        },
        evidenceCoverage=round(evidence_coverage, 2),
        warnings=warnings,
    )


MAX_LATE_HOURS_FOR_SCORE = 48.0


PROFESSIONAL_SCORE_WEIGHTS = {
    "workflowProgressionScore": 0.25,
    "deadlineScore": 0.40,
    "qualityScore": 0.35,
}


def calculate_workflow_progression_score(
    workflow_data: dict[str, Any],
) -> tuple[float | None, dict[str, float | None], float]:
    progression_rate = workflow_data.get("workflowProgressionRate")
    evaluated_cards = workflow_data.get("evaluatedCards")

    progression_score = (
        clamp(progression_rate * 100.0)
        if progression_rate is not None
        else None
    )

    evidence = 1.0 if evaluated_cards and progression_score is not None else 0.0

    return progression_score, {
        "workflowStageCoverageScore": round_score(progression_score),
    }, evidence


def calculate_deadline_score(
    deadline_data: dict[str, Any],
) -> tuple[float | None, dict[str, float | None], float, list[str]]:
    warnings: list[str] = []

    eligible_cards = deadline_data.get("deliveryEligibleCards")
    delivery_rate = deadline_data.get("deliveryRate")
    on_time_rate = deadline_data.get("onTimeRate")
    late_cards = deadline_data.get("lateCards")
    overdue_open_cards = deadline_data.get("overdueOpenCards", 0)
    avg_late_hours = deadline_data.get("avgLateHours")

    if overdue_open_cards:
        warnings.append(
            f"{overdue_open_cards} card(s) vencido(s) permaneceu(ram) aberto(s) no fechamento da janela."
        )

    if not eligible_cards:
        warnings.append(
            "DeadlineScore não calculado porque nenhuma obrigação tinha prazo vencendo até o fim da janela."
        )
        return None, {
            "deliveryScore": None,
            "deadlineOnTimeScore": None,
            "deadlineLateSeverityScore": None,
        }, 0.0, warnings

    delivery_score = (
        clamp(delivery_rate * 100.0)
        if delivery_rate is not None
        else None
    )
    on_time_score = (
        clamp(on_time_rate * 100.0)
        if on_time_rate is not None
        else None
    )

    if late_cards == 0:
        late_severity_score = 100.0
    elif avg_late_hours is None:
        late_severity_score = None
    else:
        late_severity_score = linear_score(
            avg_late_hours,
            min_value=0.0,
            max_value=MAX_LATE_HOURS_FOR_SCORE,
            invert=True,
        )

    deadline_score, evidence = weighted_score({
        "deliveryScore": (
            delivery_score,
            0.40,
        ),
        "deadlineOnTimeScore": (
            on_time_score,
            0.40,
        ),
        "deadlineLateSeverityScore": (
            late_severity_score,
            0.20,
        ),
    })

    return deadline_score, {
        "deliveryScore": round_score(delivery_score),
        "deadlineOnTimeScore": round_score(on_time_score),
        "deadlineLateSeverityScore": round_score(late_severity_score),
    }, evidence, warnings


def calculate_quality_score(
    quality_data: dict[str, Any],
) -> tuple[float | None, dict[str, float | None], float]:
    rework_rate = quality_data.get("reworkRate")
    checklist_issue_rate = quality_data.get("checklistIssueRate")

    rework_score = (
        clamp((1.0 - rework_rate) * 100.0)
        if rework_rate is not None
        else None
    )
    checklist_score = (
        clamp((1.0 - checklist_issue_rate) * 100.0)
        if checklist_issue_rate is not None
        else None
    )

    quality_score, evidence = weighted_score({
        "reworkScore": (
            rework_score,
            0.60,
        ),
        "checklistScore": (
            checklist_score,
            0.40,
        ),
    })

    return quality_score, {
        "reworkScore": round_score(rework_score),
        "checklistScore": round_score(checklist_score),
    }, evidence


def calculate_professional_score(
    professional_metrics_data: dict[str, Any],
) -> ScoreResult:
    warnings: list[str] = []

    user_id = professional_metrics_data.get("userId", "")
    date = professional_metrics_data.get("date", "")
    professional_metrics = professional_metrics_data.get(
        "professionalMetrics",
        {},
    )

    (
        workflow_progression_score,
        workflow_components,
        workflow_evidence,
    ) = calculate_workflow_progression_score(
        professional_metrics.get("workflowProgression", {})
    )

    (
        deadline_score,
        deadline_components,
        deadline_evidence,
        deadline_warnings,
    ) = calculate_deadline_score(
        professional_metrics.get("deadline", {})
    )

    (
        quality_score,
        quality_components,
        quality_evidence,
    ) = calculate_quality_score(
        professional_metrics.get("quality", {})
    )

    warnings.extend(deadline_warnings)

    if workflow_progression_score is None:
        warnings.append(
            "WorkflowProgressionScore não calculado porque não houve card concluído avaliável no período."
        )
    if quality_score is None:
        warnings.append(
            "QualityScore não calculado por falta de dados de qualidade."
        )

    professional_score, evidence_coverage = weighted_score_with_evidence({
        "workflowProgressionScore": (
            workflow_progression_score,
            PROFESSIONAL_SCORE_WEIGHTS["workflowProgressionScore"],
            workflow_evidence,
        ),
        "deadlineScore": (
            deadline_score,
            PROFESSIONAL_SCORE_WEIGHTS["deadlineScore"],
            deadline_evidence,
        ),
        "qualityScore": (
            quality_score,
            PROFESSIONAL_SCORE_WEIGHTS["qualityScore"],
            quality_evidence,
        ),
    })

    return ScoreResult(
        userId=user_id,
        date=date,
        score=round_score(professional_score),
        components={
            "workflowProgressionScore": round_score(
                workflow_progression_score
            ),
            "deadlineScore": round_score(deadline_score),
            "qualityScore": round_score(quality_score),
            **workflow_components,
            **deadline_components,
            **quality_components,
        },
        evidenceCoverage=round(evidence_coverage, 2),
        warnings=warnings,
    )

