import chromadb
import anthropic
from dotenv import load_dotenv
load_dotenv()
from pypdf import PdfReader
from docx import Document
import os
import json

def read_docx(path):
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n\n".join(paragraphs)

def read_pdf(path):
    reader = PdfReader(path)
    pages = [page.extract_text() for page in reader.pages]
    return "\n\n".join(pages)

def load_file(path):
    ext = os.path.splitext(path)[1]

    if ext == ".md":
        with open(path) as f:
            return f.read()
    elif ext == ".docx":
        return read_docx(path)
    elif ext == ".pdf":
        return read_pdf(path)
    else:
        return None

def chunk_text(text, filename):
    pieces = text.split("\n\n")
    pieces = [p.strip() for p in pieces if p.strip()]

    if filename == "customer-faq.md":
        pieces = [p for p in pieces if p.startswith("**Q:")]

    return pieces
with open("data/metadata.json") as f:
    metadata = json.load(f)

# Initialize ChromaDB client and collection
client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection("knowledge_base")

# Load and chunk every supported file in data/, skipping formats load_file doesn't handle (.csv, .json, .png)
all_chunks = []
all_ids = []
all_metadatas = []

for filename in os.listdir("data"):
    path = os.path.join("data", filename)

    file_meta = metadata.get(filename)
    if file_meta is None or file_meta["route"] != "rag":
        continue
    
    text = load_file(path)
    if text is None:
        continue

    pieces = chunk_text(text, filename)
    for i, piece in enumerate(pieces):
        all_chunks.append(piece)
        all_ids.append(f"{filename}-chunk-{i}")
        all_metadatas.append({
            "source_file": filename,
            "audience": ",".join(file_meta["audience"]), # Chroma metadata values must be str/int/float/bool, not a list
            "source_system": file_meta["source_system"],
        })

collection.upsert(
    ids=all_ids,
    documents=all_chunks,
    metadatas=all_metadatas
)

print(collection.count())

question = "Is a dripping tap covered by warranty?"
results = collection.query(
    query_texts=[question],
    n_results=3
)
DISTANCE_THRESHOLD = 1.6

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
