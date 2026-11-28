# Funções extraídas dos notebooks existentes; sem execução de I/O.
import json


from collections import defaultdict


from datetime import date, datetime


from typing import Any


from zoneinfo import ZoneInfo


APP_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def load_trello_log(file_path: str) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def parse_trello_datetime(value: str | None) -> datetime | None:
    """Converte ISO 8601 do Trello para datetime timezone-aware."""
    if not value:
        return None

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=APP_TIMEZONE)

    return parsed


def get_date(value: str | None) -> str | None:
    """Retorna a data no fuso da aplicação, evitando deslocamento de dia por UTC."""
    parsed = parse_trello_datetime(value)
    if parsed is None:
        return None

    return parsed.astimezone(APP_TIMEZONE).date().isoformat()


def parse_date(value: str | date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(APP_TIMEZONE).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


DONE_LIST_NAMES = {
    "concluído",
    "concluido",
    "done",
    "finalizado",
    "finalizada",
}


START_LIST_NAMES = {
    "a fazer",
    "to do",
    "todo",
    "backlog",
}


DEFAULT_WORKFLOW_INTERMEDIATE_STAGES = ["Em Andamento"]


def infer_workflow_intermediate_stages(trello_data: dict[str, Any]) -> list[str]:
    """
    Descobre as etapas intermediárias configuradas no board.

    Usa a ordem das listas quando ela está disponível no export. Se o arquivo não
    trouxer `lists`, mantém o fluxo atual do cenário simulado: A Fazer -> Em Andamento
    -> Concluído.
    """
    board_lists = [
        item
        for item in trello_data.get("lists", []) or []
        if item.get("name") and not item.get("closed", False)
    ]

    if board_lists:
        board_lists = sorted(
            board_lists,
            key=lambda item: item.get("pos", 0),
        )
        stages = [
            item["name"]
            for item in board_lists
            if normalize_list_name(item.get("name")) not in START_LIST_NAMES
            and not is_done_list(item.get("name"))
        ]
        if stages:
            return stages

    return DEFAULT_WORKFLOW_INTERMEDIATE_STAGES.copy()


def get_member_info(member: dict | None) -> dict:
    if not member:
        return {
            "userId": None,
            "userName": None,
            "username": None,
        }

    return {
        "userId": member.get("id"),
        "userName": member.get("fullName") or member.get("name"),
        "username": member.get("username"),
    }


def normalize_list_name(name: str | None) -> str:
    return (name or "").strip().lower()


def is_done_list(list_name: str | None) -> bool:
    return normalize_list_name(list_name) in DONE_LIST_NAMES


def build_card_index(trello_data: dict[str, Any]) -> dict[str, dict]:
    return {
        card["id"]: card
        for card in trello_data.get("cards", [])
        if card.get("id")
    }


def build_member_index(trello_data: dict[str, Any]) -> dict[str, dict]:
    """Monta o índice com members do board e membros encontrados nas actions."""
    members: dict[str, dict] = {}

    for member in trello_data.get("members", []) or []:
        member_id = member.get("id")
        if member_id:
            members[member_id] = get_member_info(member)

    for action in trello_data.get("actions", []) or []:
        candidates = [
            action.get("member"),
            action.get("memberCreator"),
            (action.get("data") or {}).get("member"),
        ]

        for member in candidates:
            if not member or not member.get("id"):
                continue

            current = members.get(member["id"], {})
            info = get_member_info(member)
            members[member["id"]] = {
                "userId": member["id"],
                "userName": info.get("userName") or current.get("userName"),
                "username": info.get("username") or current.get("username"),
            }

    return members


def get_card_from_action(action: dict) -> dict:
    return (action.get("data") or {}).get("card", {}) or {}


def get_card_id_from_action(action: dict) -> str | None:
    return get_card_from_action(action).get("id")


def get_card_name_from_action(action: dict) -> str | None:
    return get_card_from_action(action).get("name")


def _new_card_state() -> dict:
    return {
        "memberIds": set(),
        "due": None,
        "hasChecklist": False,
        "checkItems": {},
    }


def _member_fields(member_id: str | None, member_index: dict[str, dict]) -> dict:
    member = member_index.get(member_id or "", {})
    return {
        "responsibleId": member_id,
        "responsibleName": member.get("userName"),
        "responsibleUsername": member.get("username"),
    }


def _resolve_responsible(
    state: dict,
    actor_id: str | None,
    member_index: dict[str, dict],
    override_member_id: str | None = None,
) -> dict:
    """
    Resolve o responsável no instante da action.

    Evita usar idMembers do estado final exportado do card. Em cards com mais de um membro,
    prefere o ator quando ele também é membro; caso contrário deixa sem responsável único.
    """
    if override_member_id:
        return _member_fields(override_member_id, member_index)

    member_ids = set(state.get("memberIds") or set())

    if len(member_ids) == 1:
        return _member_fields(next(iter(member_ids)), member_index)

    if actor_id and actor_id in member_ids:
        return _member_fields(actor_id, member_index)

    # Ator da action não é automaticamente responsável pelo card.
    # Sem atribuição observável, preserva-se a ausência de evidência.
    return _member_fields(None, member_index)


def _snapshot_checklist(state: dict) -> dict:
    items: dict[str, str | None] = state.get("checkItems") or {}
    has_checklist = bool(state.get("hasChecklist"))
    evidence_available = bool(items)

    if not evidence_available:
        return {
            "checklistObserved": has_checklist,
            "checklistEvidenceAvailable": False,
            "checkItems": None,
            "checkItemsChecked": None,
            "checkItemsIncomplete": None,
            "checklistCompletionRate": None,
        }

    total = len(items)
    checked = sum(1 for item_state in items.values() if str(item_state).lower() == "complete")
    incomplete = total - checked

    return {
        "checklistObserved": has_checklist,
        "checklistEvidenceAvailable": True,
        "checkItems": total,
        "checkItemsChecked": checked,
        "checkItemsIncomplete": incomplete,
        "checklistCompletionRate": round(checked / total, 4),
    }


def get_last_completion_by_card(completed_events: list[dict]) -> list[dict]:
    last_by_card: dict[str, dict] = {}

    for event in completed_events:
        card_id = event.get("cardId")
        current_date = parse_trello_datetime(event.get("dateTime"))
        if not card_id or current_date is None:
            continue

        previous_event = last_by_card.get(card_id)
        previous_date = (
            parse_trello_datetime(previous_event.get("dateTime"))
            if previous_event
            else None
        )

        if previous_date is None or current_date > previous_date:
            last_by_card[card_id] = event

    return list(last_by_card.values())


def create_normalized_event(
    action: dict,
    event_type: str,
    state: dict,
    member_index: dict[str, dict],
    extra: dict | None = None,
    responsible_override: str | None = None,
) -> dict:
    actor = get_member_info(action.get("memberCreator"))
    responsible = _resolve_responsible(
        state=state,
        actor_id=actor.get("userId"),
        member_index=member_index,
        override_member_id=responsible_override,
    )

    event = {
        "actionId": action.get("id"),
        "eventType": event_type,
        "dateTime": action.get("date"),
        "date": get_date(action.get("date")),
        "cardId": get_card_id_from_action(action),
        "cardName": get_card_name_from_action(action),
        "actorId": actor.get("userId"),
        "actorName": actor.get("userName"),
        "actorUsername": actor.get("username"),
        **responsible,
    }

    if extra:
        event.update(extra)

    return event


def extract_trello_events(trello_data: dict[str, Any]) -> list[dict]:
    """
    Normaliza as actions reconstruindo estado cronologicamente.

    O responsável, o prazo e o checklist são avaliados no momento da action, evitando
    usar o estado final do card exportado pelo Trello para eventos históricos.
    """
    actions = sorted(
        trello_data.get("actions", []) or [],
        key=lambda action: action.get("date") or "",
    )
    member_index = build_member_index(trello_data)
    card_states: dict[str, dict] = defaultdict(_new_card_state)
    events: list[dict] = []

    for action in actions:
        action_type = action.get("type")
        data = action.get("data") or {}
        old = data.get("old") or {}
        card = data.get("card") or {}
        card_id = card.get("id")

        if not card_id:
            continue

        state = card_states[card_id]

        # Alguns createCard trazem membros/prazo já no snapshot da própria action.
        if action_type == "createCard":
            for member_id in card.get("idMembers") or []:
                state["memberIds"].add(member_id)
            if "due" in card:
                state["due"] = card.get("due")

        # Atribuição precisa atualizar o estado antes de normalizar o evento.
        if action_type == "addMemberToCard":
            data_member = data.get("member") or {}
            assigned_member_id = data.get("idMember") or data_member.get("id")
            if assigned_member_id:
                state["memberIds"].add(assigned_member_id)

            events.append(create_normalized_event(
                action,
                "member_assigned",
                state,
                member_index,
                {
                    "assignedMemberId": assigned_member_id,
                    "assignedMemberName": data_member.get("name") or data_member.get("fullName"),
                },
                responsible_override=assigned_member_id,
            ))
            continue

        if action_type == "removeMemberFromCard":
            data_member = data.get("member") or {}
            removed_member_id = data.get("idMember") or data_member.get("id")

            events.append(create_normalized_event(
                action,
                "member_unassigned",
                state,
                member_index,
                {
                    "unassignedMemberId": removed_member_id,
                    "unassignedMemberName": data_member.get("name") or data_member.get("fullName"),
                },
                responsible_override=removed_member_id,
            ))

            if removed_member_id:
                state["memberIds"].discard(removed_member_id)
            continue

        if action_type == "createCard":
            events.append(create_normalized_event(
                action,
                "card_created",
                state,
                member_index,
                {"listName": (data.get("list") or {}).get("name")},
            ))
            continue

        if action_type == "commentCard":
            events.append(create_normalized_event(
                action,
                "card_comment",
                state,
                member_index,
                {"commentText": data.get("text", "")},
            ))
            continue

        if action_type == "addChecklistToCard":
            checklist = data.get("checklist") or {}
            state["hasChecklist"] = True

            for item in checklist.get("checkItems") or []:
                item_id = item.get("id")
                if item_id:
                    state["checkItems"][item_id] = item.get("state")

            events.append(create_normalized_event(
                action,
                "checklist_added",
                state,
                member_index,
                {
                    "checklistId": checklist.get("id"),
                    "checklistName": checklist.get("name"),
                },
            ))
            continue

        if action_type == "updateCheckItemStateOnCard":
            check_item = data.get("checkItem") or {}
            state["hasChecklist"] = True
            item_id = check_item.get("id")
            if item_id:
                state["checkItems"][item_id] = check_item.get("state")

            events.append(create_normalized_event(
                action,
                "check_item_updated",
                state,
                member_index,
                {
                    "checkItemId": item_id,
                    "checkItemName": check_item.get("name"),
                    "checkItemState": check_item.get("state"),
                },
            ))
            continue

        if action_type != "updateCard":
            continue

        # Atualização de prazo: usa o estado daquele instante, sem consultar o card final.
        if "due" in old:
            old_due = old.get("due")
            new_due = card.get("due")
            state["due"] = new_due

            events.append(create_normalized_event(
                action,
                "due_changed",
                state,
                member_index,
                {"oldDue": old_due, "newDue": new_due},
            ))
        elif state.get("due") is None and card.get("due"):
            # Fallback apenas para o snapshot contido na própria action histórica.
            state["due"] = card.get("due")

        if "idList" in old and "listBefore" in data and "listAfter" in data:
            from_list = (data.get("listBefore") or {}).get("name")
            to_list = (data.get("listAfter") or {}).get("name")

            events.append(create_normalized_event(
                action,
                "card_moved",
                state,
                member_index,
                {"fromList": from_list, "toList": to_list},
            ))

            if is_done_list(to_list):
                due = state.get("due")
                due_date = parse_trello_datetime(due)
                completed_date = parse_trello_datetime(action.get("date"))

                if due_date and completed_date:
                    is_late = completed_date > due_date
                    delay_hours = round(
                        (completed_date - due_date).total_seconds() / 3600,
                        2,
                    )
                else:
                    is_late = None
                    delay_hours = None

                events.append(create_normalized_event(
                    action,
                    "card_completed",
                    state,
                    member_index,
                    {
                        "completedAt": action.get("date"),
                        "due": due,
                        "isLate": is_late,
                        "delayHours": delay_hours,
                        **_snapshot_checklist(state),
                    },
                ))

            if is_done_list(from_list) and not is_done_list(to_list):
                events.append(create_normalized_event(
                    action,
                    "card_reopened",
                    state,
                    member_index,
                    {"fromList": from_list, "toList": to_list},
                ))

        if "dueComplete" in old:
            due_complete = card.get("dueComplete")
            events.append(create_normalized_event(
                action,
                "due_completed" if due_complete else "due_reopened",
                state,
                member_index,
                {"due": state.get("due")},
            ))

        if "closed" in old:
            closed = card.get("closed")
            events.append(create_normalized_event(
                action,
                "card_archived" if closed else "card_unarchived",
                state,
                member_index,
            ))

    return sorted(events, key=lambda event: event.get("dateTime") or "")


from collections import defaultdict


from datetime import time, timedelta


from typing import Any


def avg(values: list[float]) -> float | None:
    valid_values = [
        value
        for value in values
        if isinstance(value, (int, float))
    ]

    if not valid_values:
        return None

    return round(sum(valid_values) / len(valid_values), 4)


def _event_in_period(
    event: dict,
    start_date: str | date | datetime | None,
    end_date: str | date | datetime | None,
) -> bool:
    event_date = parse_date(event.get("date"))
    if event_date is None:
        return False

    start = parse_date(start_date)
    end = parse_date(end_date)

    if start is not None and event_date < start:
        return False
    if end is not None and event_date > end:
        return False

    return True


def _period_days(
    events: list[dict],
    start_date: str | date | datetime | None,
    end_date: str | date | datetime | None,
) -> int:
    start = parse_date(start_date)
    end = parse_date(end_date)

    if start is not None and end is not None:
        return max((end - start).days + 1, 1)

    dates = sorted({
        parse_date(event.get("date"))
        for event in events
        if event.get("date")
    })
    dates = [value for value in dates if value is not None]
    if not dates:
        return 1

    return max((dates[-1] - dates[0]).days + 1, 1)


def _build_card_states_at(
    events: list[dict],
    cutoff_date: str | date | datetime,
) -> dict[str, dict[str, Any]]:
    """
    Reconstrói o estado de cada card até o fechamento da data informada.

    Essa visão é usada para saber se uma obrigação estava realmente entregue,
    aberta ou vencida no fim da janela, sem depender do estado final do export.
    """
    cutoff = parse_date(cutoff_date)
    if cutoff is None:
        return {}

    states: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "memberIds": set(),
        "due": None,
        "listName": None,
        "lastCompletionAt": None,
        "lastEventDate": None,
    })

    for event in sorted(events, key=lambda item: item.get("dateTime") or ""):
        event_date = parse_date(event.get("date"))
        if event_date is None or event_date > cutoff:
            continue

        card_id = event.get("cardId")
        if not card_id:
            continue

        state = states[card_id]
        state["lastEventDate"] = event.get("date")
        event_type = event.get("eventType")

        if event_type == "card_created":
            state["listName"] = event.get("listName") or state.get("listName")

        elif event_type == "member_assigned":
            member_id = event.get("assignedMemberId")
            if member_id:
                state["memberIds"].add(member_id)

        elif event_type == "member_unassigned":
            member_id = event.get("unassignedMemberId")
            if member_id:
                state["memberIds"].discard(member_id)

        elif event_type == "due_changed":
            state["due"] = event.get("newDue")

        elif event_type == "card_moved":
            state["listName"] = event.get("toList") or state.get("listName")

        elif event_type == "card_completed":
            state["lastCompletionAt"] = event.get("completedAt") or event.get("dateTime")
            if state.get("due") is None and event.get("due"):
                state["due"] = event.get("due")

        elif event_type == "card_reopened":
            state["listName"] = event.get("toList") or state.get("listName")

    return dict(states)


def _latest_completion_by_card_until(
    events: list[dict],
    cutoff_date: str | date | datetime,
) -> dict[str, dict]:
    cutoff = parse_date(cutoff_date)
    result: dict[str, dict] = {}

    if cutoff is None:
        return result

    for event in events:
        if event.get("eventType") != "card_completed":
            continue

        event_date = parse_date(event.get("date"))
        card_id = event.get("cardId")
        if event_date is None or event_date > cutoff or not card_id:
            continue

        current = result.get(card_id)
        if (
            current is None
            or (event.get("dateTime") or "") > (current.get("dateTime") or "")
        ):
            result[card_id] = event

    return result


def _workflow_stage_index(
    stage_name: str | None,
    workflow_intermediate_stages: list[str],
) -> int | None:
    ordered = [
        "A Fazer",
        *workflow_intermediate_stages,
        "Concluído",
    ]
    normalized = [normalize_list_name(stage) for stage in ordered]
    current = normalize_list_name(stage_name)

    if current in normalized:
        return normalized.index(current)

    if is_done_list(stage_name):
        return len(ordered) - 1

    if current in START_LIST_NAMES:
        return 0

    return None


def _is_backward_workflow_move(
    event: dict,
    workflow_intermediate_stages: list[str],
) -> bool:
    if event.get("eventType") != "card_moved":
        return False

    from_index = _workflow_stage_index(
        event.get("fromList"),
        workflow_intermediate_stages,
    )
    to_index = _workflow_stage_index(
        event.get("toList"),
        workflow_intermediate_stages,
    )

    return (
        from_index is not None
        and to_index is not None
        and to_index < from_index
    )


def _workflow_path_until_completion(
    all_events: list[dict],
    card_id: str,
    completion_event: dict,
) -> list[str]:
    completion_time = completion_event.get("dateTime") or ""
    path: list[str] = []

    card_events = [
        event
        for event in all_events
        if event.get("cardId") == card_id
        and (event.get("dateTime") or "") <= completion_time
    ]

    for event in sorted(card_events, key=lambda item: item.get("dateTime") or ""):
        stage = None
        if event.get("eventType") == "card_created":
            stage = event.get("listName")
        elif event.get("eventType") == "card_moved":
            stage = event.get("toList")

        if stage and (not path or normalize_list_name(path[-1]) != normalize_list_name(stage)):
            path.append(stage)

    return path


def _calculate_workflow_progression(
    all_events: list[dict],
    completed_events: list[dict],
    workflow_intermediate_stages: list[str],
) -> dict[str, Any]:
    """
    Mede a cobertura das etapas intermediárias esperadas em cada card concluído.

    Repetir movimentos não aumenta o indicador: cada etapa esperada conta no máximo
    uma vez por card. Retornos de etapa são tratados separadamente como possível
    retrabalho em qualidade.
    """
    expected = [
        normalize_list_name(stage)
        for stage in workflow_intermediate_stages
        if normalize_list_name(stage)
    ]

    if not completed_events or not expected:
        return {
            "evaluatedCards": len(completed_events),
            "expectedIntermediateStages": workflow_intermediate_stages,
            "workflowProgressionRate": None,
            "fullProgressionCards": None,
            "directCompletionCards": None,
            "cardProgressions": [],
        }

    card_progressions = []

    for completion in completed_events:
        card_id = completion.get("cardId")
        if not card_id:
            continue

        path = _workflow_path_until_completion(
            all_events,
            card_id,
            completion,
        )
        visited = {
            normalize_list_name(stage)
            for stage in path
        }

        covered = [
            stage
            for stage in expected
            if stage in visited
        ]
        coverage = len(covered) / len(expected)

        card_progressions.append({
            "cardId": card_id,
            "path": path,
            "coveredIntermediateStages": covered,
            "expectedIntermediateStages": expected,
            "coverage": round(coverage, 4),
        })

    if not card_progressions:
        rate = None
        full_count = None
        direct_count = None
    else:
        rate = round(
            sum(item["coverage"] for item in card_progressions)
            / len(card_progressions),
            4,
        )
        full_count = sum(
            1 for item in card_progressions
            if item["coverage"] == 1.0
        )
        direct_count = sum(
            1 for item in card_progressions
            if item["coverage"] == 0.0
        )

    return {
        "evaluatedCards": len(card_progressions),
        "expectedIntermediateStages": workflow_intermediate_stages,
        "workflowProgressionRate": rate,
        "fullProgressionCards": full_count,
        "directCompletionCards": direct_count,
        "cardProgressions": card_progressions,
    }


def _end_of_day(end_date: str | date | datetime) -> datetime:
    parsed = parse_date(end_date)
    if parsed is None:
        raise ValueError("end_date é obrigatório para calcular atraso de cards abertos.")
    return datetime.combine(parsed, time.max, tzinfo=APP_TIMEZONE)


def aggregate_trello_indicators_by_user(
    events: list[dict],
    start_date: str | date | datetime | None = None,
    end_date: str | date | datetime | None = None,
    workflow_intermediate_stages: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Agrega os indicadores profissionais por janela.

    - WorkflowProgression: cobertura das etapas intermediárias nos cards concluídos;
    - Delivery: usa apenas obrigações cujo prazo já chegou até o fim da janela;
    - Deadline: inclui cards vencidos que permanecem abertos no fechamento;
    - Quality: retrabalho por cards únicos e checklist somente quando observável;
    - histórico completo calcula a duração individual de cada usuário.
    """
    workflow_intermediate_stages = (
        workflow_intermediate_stages
        if workflow_intermediate_stages is not None
        else DEFAULT_WORKFLOW_INTERMEDIATE_STAGES
    )

    period_events = [
        event
        for event in events
        if _event_in_period(event, start_date, end_date)
    ]

    # Para janelas explícitas, estados de início/fim permitem avaliar obrigações reais,
    # inclusive cards criados antes da janela ou sem actions durante o período.
    explicit_window = start_date is not None and end_date is not None
    end_states = (
        _build_card_states_at(events, end_date)
        if explicit_window
        else {}
    )
    start = parse_date(start_date)
    end = parse_date(end_date)

    if explicit_window and start is not None:
        start_states = _build_card_states_at(
            events,
            start - timedelta(days=1),
        )
    else:
        start_states = {}

    latest_completion_at_end = (
        _latest_completion_by_card_until(events, end_date)
        if explicit_window
        else {}
    )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in period_events:
        responsible_id = event.get("responsibleId")
        if responsible_id:
            grouped[responsible_id].append(event)

    # Inclui responsáveis que podem ter obrigação vencida no fim da janela mesmo sem
    # qualquer action registrada naquele período.
    if explicit_window:
        for state in end_states.values():
            for member_id in state.get("memberIds") or set():
                grouped.setdefault(member_id, [])

    results: dict[str, dict[str, Any]] = {}

    for user_id, user_events in grouped.items():
        user_events = sorted(user_events, key=lambda event: event.get("dateTime") or "")
        all_user_events = [
            event
            for event in events
            if event.get("responsibleId") == user_id
        ]

        first_event = (
            user_events[0]
            if user_events
            else next(
                (
                    event
                    for event in reversed(events)
                    if event.get("responsibleId") == user_id
                ),
                {},
            )
        )

        period_days = _period_days(
            user_events if user_events else all_user_events,
            start_date,
            end_date,
        )

        completed_events = [
            event
            for event in user_events
            if event.get("eventType") == "card_completed"
        ]
        unique_completed_cards = get_last_completion_by_card(completed_events)
        completed_card_ids = {
            event.get("cardId")
            for event in unique_completed_cards
            if event.get("cardId")
        }

        workflow_metrics = _calculate_workflow_progression(
            all_events=events,
            completed_events=unique_completed_cards,
            workflow_intermediate_stages=workflow_intermediate_stages,
        )

        moved_events = [
            event
            for event in user_events
            if event.get("eventType") == "card_moved"
        ]
        backward_move_card_ids = {
            event.get("cardId")
            for event in moved_events
            if event.get("cardId")
            and _is_backward_workflow_move(
                event,
                workflow_intermediate_stages,
            )
        }
        reopened_card_ids = {
            event.get("cardId")
            for event in user_events
            if event.get("eventType") == "card_reopened"
            and event.get("cardId")
        }
        rework_card_ids = reopened_card_ids | backward_move_card_ids

        # ------------------------------------------------------------------
        # Delivery + Deadline
        # ------------------------------------------------------------------
        delivery_eligible_card_ids: set[str] = set()
        delivered_card_ids: set[str] = set()
        overdue_open_card_ids: set[str] = set()

        if explicit_window and start is not None and end is not None:
            for card_id, state in end_states.items():
                if user_id not in (state.get("memberIds") or set()):
                    continue

                due = state.get("due")
                due_dt = parse_trello_datetime(due)
                if due_dt is None:
                    continue

                due_date = due_dt.astimezone(APP_TIMEZONE).date()

                # Prazo futuro: ainda não houve oportunidade real de entrega.
                if due_date > end:
                    continue

                start_state = start_states.get(card_id, {})
                was_done_before_window = is_done_list(start_state.get("listName"))

                # Tarefa já encerrada antes da janela e cujo prazo também era anterior
                # não pertence mais ao período atual.
                if due_date < start and was_done_before_window:
                    continue

                delivery_eligible_card_ids.add(card_id)

                if is_done_list(state.get("listName")):
                    delivered_card_ids.add(card_id)
                else:
                    overdue_open_card_ids.add(card_id)

        else:
            # Histórico completo: delivery é descritivo, baseado nas conclusões observadas.
            delivery_eligible_card_ids = set(completed_card_ids)
            delivered_card_ids = set(completed_card_ids)

        delivery_rate = (
            round(
                len(delivered_card_ids)
                / len(delivery_eligible_card_ids),
                4,
            )
            if delivery_eligible_card_ids
            else None
        )

        on_time_card_ids: set[str] = set()
        late_completed_card_ids: set[str] = set()
        late_hours: list[float] = []

        if explicit_window and end is not None:
            for card_id in delivered_card_ids:
                completion = latest_completion_at_end.get(card_id)
                if not completion:
                    continue

                if completion.get("isLate") is True:
                    late_completed_card_ids.add(card_id)
                    delay = completion.get("delayHours")
                    if isinstance(delay, (int, float)) and delay > 0:
                        late_hours.append(float(delay))
                elif completion.get("isLate") is False:
                    on_time_card_ids.add(card_id)

            cutoff = _end_of_day(end_date)
            for card_id in overdue_open_card_ids:
                due = end_states.get(card_id, {}).get("due")
                due_dt = parse_trello_datetime(due)
                if due_dt is None:
                    continue

                due_local = due_dt.astimezone(APP_TIMEZONE)
                current_delay = (cutoff - due_local).total_seconds() / 3600
                if current_delay > 0:
                    late_hours.append(round(current_delay, 2))
        else:
            for completion in unique_completed_cards:
                card_id = completion.get("cardId")
                if not card_id:
                    continue
                if completion.get("isLate") is True:
                    late_completed_card_ids.add(card_id)
                    delay = completion.get("delayHours")
                    if isinstance(delay, (int, float)) and delay > 0:
                        late_hours.append(float(delay))
                elif completion.get("isLate") is False:
                    on_time_card_ids.add(card_id)

        # Pontualidade mede somente obrigações entregues; se havia obrigação mas nenhuma
        # foi entregue, operacionalmente a pontualidade no período é zero.
        if delivered_card_ids:
            on_time_rate = round(
                len(on_time_card_ids) / len(delivered_card_ids),
                4,
            )
        elif delivery_eligible_card_ids:
            on_time_rate = 0.0
        else:
            on_time_rate = None

        late_card_ids = late_completed_card_ids | overdue_open_card_ids
        avg_late_hours = avg(late_hours)

        # ------------------------------------------------------------------
        # Quality
        # ------------------------------------------------------------------
        completed_with_checklist = [
            event
            for event in unique_completed_cards
            if event.get("checklistEvidenceAvailable") is True
        ]
        incomplete_checklists = [
            event
            for event in completed_with_checklist
            if isinstance(event.get("checkItemsIncomplete"), (int, float))
            and event.get("checkItemsIncomplete", 0) > 0
        ]
        checklist_issue_rate = (
            round(
                len(incomplete_checklists)
                / len(completed_with_checklist),
                4,
            )
            if completed_with_checklist
            else None
        )

        quality_observed_card_ids = completed_card_ids | rework_card_ids
        rework_rate = (
            round(
                len(rework_card_ids)
                / len(quality_observed_card_ids),
                4,
            )
            if quality_observed_card_ids
            else None
        )

        results[user_id] = {
            "userName": first_event.get("responsibleName"),
            "username": first_event.get("responsibleUsername"),
            "dates": sorted({
                event.get("date")
                for event in user_events
                if event.get("date")
            }),
            "period": {
                "startDate": str(parse_date(start_date)) if start_date else None,
                "endDate": str(parse_date(end_date)) if end_date else None,
                "days": period_days,
            },
            "professionalMetrics": {
                "workflowProgression": workflow_metrics,
                "deadline": {
                    "deliveryEligibleCards": len(delivery_eligible_card_ids),
                    "deliveredCards": len(delivered_card_ids),
                    "deliveryRate": delivery_rate,
                    "onTimeCards": len(on_time_card_ids),
                    "lateCompletedCards": len(late_completed_card_ids),
                    "overdueOpenCards": len(overdue_open_card_ids),
                    "lateCards": len(late_card_ids),
                    "onTimeRate": on_time_rate,
                    "avgLateHours": avg_late_hours,
                },
                "quality": {
                    "qualityObservedCards": len(quality_observed_card_ids),
                    "reworkCards": len(rework_card_ids),
                    "reopenedCards": len(reopened_card_ids),
                    "backwardWorkflowCards": len(backward_move_card_ids),
                    "reworkRate": rework_rate,
                    "completedWithChecklist": len(completed_with_checklist),
                    "completedWithIncompleteChecklist": len(incomplete_checklists),
                    "checklistIssueRate": checklist_issue_rate,
                },
            },
        }

    return dict(sorted(results.items()))

