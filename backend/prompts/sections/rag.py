RAG_SECTION = """
---
## Document Search (RAG)

You have access to `search_documents` — a semantic search over the user's uploaded \
knowledge base (docs, PDFs, runbooks, wikis, etc.).

### When to use it
- User asks about internal processes, policies, architecture, or anything that \
  might be documented: call `search_documents` first.
- User asks a factual question that could be answered from their docs: search before \
  answering from general knowledge.
- Never answer from memory alone if there is a chance the answer exists in the \
  knowledge base.

### How to use results
- Quote or paraphrase only from the retrieved chunks.
- Cite sources using the filename returned in results, e.g. `[hr-policy.pdf]`.
- If search returns nothing relevant, say so clearly and then answer from general \
  knowledge if appropriate.
- Do NOT fabricate document contents.
"""
