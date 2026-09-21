import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

def load_trello_log(file_path: str) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)
    
trello_data = load_trello_log("Teste1-Trello.json")

# Converte data de ISO 8601 pra datetime, trata Z como UTC
def parse_trello_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))

# Retorna data sem hora, no formato YYYY-MM-DD
def get_date(value: str) -> str:
    return parse_trello_datetime(value).date().isoformat()


"""
Extrai todos os usuários que aparecem nos logs (actions) e cria um índice de membros.
Ou seja, relaciona cada card com os membros que o movimentaram.
"""
def build_member_index(actions: list[dict]) -> dict[str, dict]:
    members = {}

    for action in actions:
        for key in ["member", "memberCreator"]:
            member = action.get(key)

            if member and member.get("id"):
                members[member["id"]] = {
                    "userId": member.get("id"),
                    "userName": member.get("fullName") or member.get("name"),
                    "username": member.get("username")
                }

        data_member = action.get("data", {}).get("member")

        if data_member and data_member.get("id"):
            members[data_member["id"]] = {
                "userId": data_member.get("id"),
                "userName": data_member.get("name"),
                "username": None
            }
               
    return members

build_member_index(trello_data.get("actions", []))