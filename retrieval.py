import chromadb
import anthropic
from dotenv import load_dotenv
load_dotenv()

DISTANCE_THRESHOLD = 1.6

def retrieve_relevant_chunks(collection, question, n_results=3, distance_threshold=DISTANCE_THRESHOLD):
    results = collection.query(query_texts=[question], n_results=n_results)

    return [
        {"text": doc, "distance": dist, "metadata": meta}
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        )
        if dist <= distance_threshold
    ]

if __name__ == "__main__":
    client = chromadb.PersistentClient(path="./chroma_data")
    collection = client.get_or_create_collection("knowledge_base")

    question = "Is a dripping tap covered by warranty?"
    relevant_chunks = retrieve_relevant_chunks(collection, question)

    context = "\n\n".join(chunk["text"] for chunk in relevant_chunks)

    anthropic_client = anthropic.Anthropic()

    prompt = f"""Answer the customer's question using only the context below. If the context doesn't contain the answer, say you don't know.

Context:
{context}

Question: {question}"""

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    print(response.content[0].text)
