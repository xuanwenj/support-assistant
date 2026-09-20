import chromadb
# Script to read and split the customer FAQ markdown file into chunks
with open("data/customer-faq.md") as f:
    text = f.read()

chunks = text.split("\n\n")
chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
chunks = [chunk for chunk in chunks if chunk.startswith("**Q:")]


print(len(chunks))


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

results = collection.query(
    query_texts=["Is a dripping tap covered by warranty?"],
    # query_texts=[ "How do I bake bread?"],
    n_results=3
)
DISTANCE_THRESHOLD = 1.8

relevant_chunks = [
    doc for doc, distance in zip(results["documents"][0], results["distances"][0])
    if distance <= DISTANCE_THRESHOLD
]

print(len(relevant_chunks))
for chunk in relevant_chunks:
    print("---")
    print(chunk)