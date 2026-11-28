
import json
from datetime import datetime, timezone
from pathlib import Path

from groq import Groq, APIStatusError

client = Groq()

# --------------------------------------------------
# Prompt
# --------------------------------------------------

prompt = """
Simule os registros de mensagens enviadas por um mesmo colaborador a um assistente virtual durante cinco dias de sua rotina de trabalho, de 4 a 8 de maio de 2026.

**Contexto de trabalho**

O colaborador participa da manutenção e evolução de um sistema interno de atendimento. Suas atividades envolvem investigar chamados, esclarecer dúvidas técnicas, corrigir inconsistências nos relatórios, testar alterações e preparar uma atualização do sistema.

Essas atividades podem apresentar avanços, dificuldades, interrupções, mudanças de prioridade e descobertas ao longo dos dias. Outras demandas relacionadas ao contexto de trabalho também podem surgir.

**Dinâmica das interações**

Gere mensagens que poderiam ser encontradas no histórico real de utilização de um assistente virtual por esse colaborador.

Considere que o assistente responde entre as mensagens, embora suas respostas não devam aparecer nos registros gerados. O colaborador pode comentar uma resposta recebida, esclarecer uma dúvida anterior, corrigir uma informação, complementar uma solicitação ou retomar um assunto de outro dia.

Algumas atividades devem ter continuidade ao longo do período. Outras podem ser resolvidas rapidamente ou permanecer pendentes.

As mensagens não precisam ser sempre perguntas ou solicitações completas. Elas podem conter comentários, explicações, confirmações, dúvidas, relatos e reações espontâneas ao andamento das atividades.

Preserve características gerais da comunicação do colaborador, permitindo variações naturais na escrita conforme as situações vivenciadas.

Evite transformar cada mensagem em um exemplo isolado de tarefa que poderia ser solicitada a um assistente virtual. Considere o contexto das interações anteriores e a evolução das atividades.

Não estabeleça proporções fixas de sentimentos, tipos de frase, formalidade ou extensão das mensagens.

Respeite a coerência temporal e escreva em português brasileiro. Não utilize informações pessoais reais.

**Distribuição das mensagens**

O campo "dia" representa exclusivamente a posição do dia dentro do bloco, e não o dia do mês.

- Dia 1 (04/05/2026): 6 mensagens.
- Dia 2 (05/05/2026): 8 mensagens.
- Dia 3 (06/05/2026): 5 mensagens.
- Dia 4 (07/05/2026): 7 mensagens.
- Dia 5 (08/05/2026): 7 mensagens.

Retorne os identificadores dos dias como 1, 2, 3, 4 e 5, respectivamente.

Respeite exatamente as quantidades solicitadas. Gere somente as mensagens enviadas pelo colaborador, sem incluir as respostas do assistente.
"""

# --------------------------------------------------
# Estrutura da resposta
# --------------------------------------------------

schema = {
    "type": "object",
    "properties": {
        "dias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dia": {
                        "type": "integer"
                    },
                    "mensagens": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    }
                },
                "required": ["dia", "mensagens"],
                "additionalProperties": False
            }
        }
    },
    "required": ["dias"],
    "additionalProperties": False
}

# --------------------------------------------------
# Configuração
# --------------------------------------------------

request = {
    "model": "openai/gpt-oss-120b",
    "messages": [
        {
            "role": "user",
            "content": prompt
        }
    ],
    "temperature": 0.8,
    "reasoning_effort": "low",
    "max_completion_tokens": 3000,
    "seed": 42,
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "bloco_comunicacional",
            "strict": True,
            "schema": schema
        }
    }
}

# --------------------------------------------------
# Geração
# --------------------------------------------------

try:
    response = client.chat.completions.create(**request)

    # Preservar a requisição e a resposta originais.

    output_dir = Path(__file__).resolve().parent / "piloto"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    registro = {
        "request": request,
        "response": response.model_dump(mode="json")
    }

    output = output_dir / f"bloco_{timestamp}.json"

    output.write_text(
        json.dumps(
            registro,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    # Verificação inicial do conteúdo.

    choice = response.choices[0]

    if choice.finish_reason != "stop":
        raise ValueError(
            f"Geração incompleta: {choice.finish_reason}"
        )

    data = json.loads(choice.message.content)

    esperado = {1: 6, 2: 8, 3: 5, 4: 7, 5: 7}

    dias = data["dias"]

    valido = (
        [d["dia"] for d in dias] == list(esperado)
        and all(
            len(d["mensagens"]) == esperado[d["dia"]]
            and all(m.strip() for m in d["mensagens"])
            for d in dias
        )
    )

    print("\n--- MENSAGENS GERADAS ---")

    for dia in dias:
        print(f"\nDIA {dia['dia']}")

        for mensagem in dia["mensagens"]:
            print(f"- {mensagem}")

    print("\n--- VALIDAÇÃO ---")

    for dia in dias:
        print(
            f"Dia {dia['dia']}: "
            f"{len(dia['mensagens'])} mensagens"
        )

    print(f"Distribuição válida: {valido}")

    print("\n--- INFORMAÇÕES ---")
    print(f"Modelo: {response.model}")
    print(f"Fingerprint: {response.system_fingerprint}")
    print(f"Finalização: {choice.finish_reason}")

    print("\n--- CONSUMO ---")
    print(f"Entrada: {response.usage.prompt_tokens}")
    print(f"Saída: {response.usage.completion_tokens}")
    print(f"Total: {response.usage.total_tokens}")

    print(f"\nArquivo salvo em: {output}")

except APIStatusError as e:
    print(f"Status: {e.status_code}")
    print(f"Resposta: {e.response.text}")
