import chromadb
import anthropic
from dotenv import load_dotenv
load_dotenv()

# Script to read and split the customer FAQ markdown file into chunks
with open("data/customer-faq.md") as f:
    text = f.read()

chunks = text.split("\n\n")
chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
chunks = [chunk for chunk in chunks if chunk.startswith("**Q:")]


# Initialize ChromaDB client and collection
client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection("customer_faq_docs")

# print(collection.count())  # pre-upsert check from Step 3, no longer needed

# add the chunks to the collection
ids = [f"chunk-{i}" for i in range(len(chunks))]

collection.upsert(
    ids=ids,
    documents=chunks
)

print(collection.count())  # confirms how many items are in the collection right before we query it
question = "Is a dripping tap covered by warranty?"
results = collection.query(
    query_texts=[question],
    n_results=3
)
DISTANCE_THRESHOLD = 1.8

relevant_chunks = [
    doc for doc, distance in zip(results["documents"][0], results["distances"][0])
    if distance <= DISTANCE_THRESHOLD
]

context = "\n\n".join(relevant_chunks)

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
