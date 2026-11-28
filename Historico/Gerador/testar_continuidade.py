
import json
from datetime import datetime, timezone
from pathlib import Path

from groq import Groq, APIStatusError

client = Groq()

# --------------------------------------------------
# Contexto do bloco anterior
# --------------------------------------------------

arquivo_anterior = (
    Path(__file__).resolve().parent
    / "piloto"
    / "bloco_20261128T073942708635Z.json"
)

registro_anterior = json.loads(
    arquivo_anterior.read_text(encoding="utf-8")
)

conteudo_anterior = json.loads(
    registro_anterior["response"]["choices"][0]
    ["message"]["content"]
)

historico = json.dumps(
    conteudo_anterior,
    ensure_ascii=False,
    indent=2
)

# --------------------------------------------------
# Prompt
# --------------------------------------------------

prompt = f"""
Simule a continuidade dos registros de mensagens
enviadas pelo mesmo colaborador a um assistente
virtual durante sua rotina de trabalho.

Gere as mensagens referentes ao período de
11 a 15 de maio de 2026.

CONTEXTO DE TRABALHO

O colaborador participa da manutenção e evolução
de um sistema interno de atendimento.

Suas atividades envolvem investigar chamados,
esclarecer dúvidas técnicas, corrigir inconsistências
nos relatórios, testar alterações e preparar
atualizações do sistema.

HISTÓRICO ANTERIOR

As mensagens abaixo foram registradas entre
4 e 8 de maio de 2026:

{historico}

DINÂMICA DAS INTERAÇÕES

Considere o histórico anterior para preservar
a continuidade da rotina profissional e as
características gerais da comunicação do colaborador.

As atividades anteriores podem ser retomadas,
concluídas, modificadas ou permanecer pendentes.
Novas demandas relacionadas ao contexto profissional
também podem surgir.

Não é necessário retomar todos os assuntos
do histórico anterior.

Considere que o assistente responde entre as
mensagens, embora suas respostas não devam aparecer
nos registros gerados.

O colaborador pode comentar respostas recebidas,
esclarecer dúvidas, corrigir informações,
complementar solicitações e retomar assuntos.

As mensagens podem conter perguntas, comentários,
explicações, confirmações, relatos e reações
espontâneas ao andamento das atividades.

Permita variações naturais na escrita e nas
interações conforme as situações vivenciadas.

Evite copiar ou reformular superficialmente
as mensagens anteriores.

Não estabeleça proporções fixas de sentimentos,
tipos de frase, formalidade ou extensão.

Respeite a coerência temporal e escreva em
português brasileiro.

Não utilize informações pessoais reais.

DISTRIBUIÇÃO DAS MENSAGENS

O campo "dia" representa exclusivamente a posição
do dia dentro do bloco, e não o dia do mês.

Dia 1 (11/05/2026): 6 mensagens.
Dia 2 (12/05/2026): 8 mensagens.
Dia 3 (13/05/2026): 5 mensagens.
Dia 4 (14/05/2026): 7 mensagens.
Dia 5 (15/05/2026): 7 mensagens.

Retorne os identificadores dos dias como
1, 2, 3, 4 e 5, respectivamente.

Respeite exatamente as quantidades solicitadas.

Gere somente as mensagens enviadas pelo colaborador,
sem incluir as respostas do assistente.
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
    "seed": 43,
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
