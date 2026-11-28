
from groq import Groq, APIStatusError

client = Groq()

try:
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": "Responda em português brasileiro."
            },
            {
                "role": "user",
                "content": (
                    "Crie cinco exemplos de mensagens naturais "
                    "enviadas por um colaborador a um assistente "
                    "virtual durante sua rotina de trabalho. "
                    "Apresente somente as mensagens."
                )
            }
        ],
        temperature=0.8,
        reasoning_effort="low",
        max_completion_tokens=1500,
        seed=42
    )

    print("\n--- RESPOSTA ---\n")
    print(response.choices[0].message.content)

    print("\n--- INFORMAÇÕES DA GERAÇÃO ---\n")
    print(f"Modelo: {response.model}")
    print(f"ID: {response.id}")
    print(f"Fingerprint: {response.system_fingerprint}")
    print(f"Finalização: {response.choices[0].finish_reason}")

    print("\n--- CONSUMO ---\n")
    print(f"Tokens de entrada: {response.usage.prompt_tokens}")
    print(f"Tokens de saída: {response.usage.completion_tokens}")
    print(f"Total de tokens: {response.usage.total_tokens}")

except APIStatusError as e:
    print("\n--- ERRO DA API ---\n")
    print(f"Status: {e.status_code}")
    print(f"Resposta: {e.response.text}")
