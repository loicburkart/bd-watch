import os

from dotenv import load_dotenv
from openai import OpenAI


# Build an OpenAI-compatible client pointed at a Databricks serving endpoint.
def get_client() -> OpenAI:
    host = os.environ["DATABRICKS_HOST"].rstrip("/")
    return OpenAI(
        api_key=os.environ["DATABRICKS_TOKEN"],
        base_url=f"{host}/serving-endpoints",
    )


# Invoke the configured serving endpoint with a single user prompt.
def main() -> None:
    load_dotenv()
    client = get_client()

    response = client.chat.completions.create(
        model=os.environ["DATABRICKS_ENDPOINT"],
        messages=[{"role": "user", "content": "Dis bonjour en une phrase."}],
        max_tokens=256,
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()