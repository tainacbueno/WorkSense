"""Teste exploratório de diversidade."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from groq import Groq, APIStatusError

HERE = Path(__file__).resolve().parent
PILOTO = HERE / "piloto"
ORIGINAL = PILOTO / "bloco_20261128T073942708635Z.json"

CONTEXTOS = [
    (
        "tecnico_nova_semente", 44,
        "O colaborador participa da manutenção e evolução de um sistema interno de atendimento. "
        "Suas atividades envolvem investigar chamados, esclarecer dúvidas técnicas, "
        "corrigir inconsistências nos relatórios, testar alterações e preparar uma atualização do sistema."
    ),
    (
        "administrativo", 45,
        "O colaborador acompanha pedidos de compra e documentos de fornecedores. "
        "Suas atividades envolvem conferir informações, organizar solicitações internas, "
        "acompanhar pendências e preparar relatórios de acompanhamento."
    ),
    (
        "atendimento", 46,
        "O colaborador acompanha solicitações de clientes sobre um serviço digital. "
        "Suas atividades envolvem esclarecer dúvidas, verificar informações de atendimento, "
        "encaminhar ocorrências a outras equipes e acompanhar casos ainda em aberto."
    ),
]

ESPERADO = {1: 6, 2: 8, 3: 5, 4: 7, 5: 7}


def preparar_requisicao(original, contexto, seed):
    request = copy.deepcopy(original)
    prompt = request["messages"][0]["content"]
    inicio = "**Contexto de trabalho**\n\n"
    fim = "\n\nEssas atividades podem apresentar"
    antes, separador, resto = prompt.partition(inicio)
    _, separador_fim, depois = resto.partition(fim)
    if not separador or not separador_fim:
        raise ValueError("O prompt original não corresponde à versão 3 esperada.")
    request["messages"][0]["content"] = antes + inicio + contexto + fim + depois
    request["seed"] = seed
    return request


def validar(dias):
    return (
        isinstance(dias, list)
        and all(isinstance(d, dict) for d in dias)
        and [d.get("dia") for d in dias] == list(ESPERADO)
        and all(
            isinstance(d.get("mensagens"), list)
            and len(d["mensagens"]) == ESPERADO[d["dia"]]
            and all(isinstance(m, str) and m.strip() for m in d["mensagens"])
            for d in dias
        )
    )


def salvar(nome, registro):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    arquivo = PILOTO / f"diversidade_{nome}_{timestamp}.json"
    arquivo.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    return arquivo


def main():
    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))["request"]
    client = Groq(max_retries=0)

    for nome, seed, contexto in CONTEXTOS:
        request = preparar_requisicao(original, contexto, seed)
        print(f"\n--- {nome} | seed={seed} ---", flush=True)
        try:
            response = client.chat.completions.create(**request)
        except APIStatusError as e:
            arquivo = salvar(nome, {
                "request": request,
                "error": {"status": e.status_code, "body": e.response.text}
            })
            print(f"Erro {e.status_code}. Registro: {arquivo}")
            return 1

        arquivo = salvar(nome, {
            "request": request,
            "response": response.model_dump(mode="json")
        })
        print(f"Arquivo salvo: {arquivo}")
        choice = response.choices[0]
        try:
            dias = json.loads(choice.message.content)["dias"]
            valido = choice.finish_reason == "stop" and validar(dias)
        except (ValueError, TypeError, KeyError):
            valido = False
            dias = []
        print(f"Distribuição válida: {valido}")
        print(f"Fingerprint: {response.system_fingerprint}")
        print(f"Finalização: {choice.finish_reason}")
        print(f"Tokens: {response.usage.total_tokens if response.usage else 'não informado'}")
        if not valido:
            print("Geração inválida preservada para análise. Nenhuma correção automática.")
            continue
        for dia in dias:
            print(f"\nDIA {dia['dia']}")
            for mensagem in dia["mensagens"]:
                print(f"- {mensagem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
