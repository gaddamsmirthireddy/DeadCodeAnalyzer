"""Retrieval logic placeholder."""
import math
import re
from collections import Counter
from dataclasses import dataclass

from app.retrieval.chunker import CodeChunk


@dataclass(frozen=True)
class ReplacementMatch:
    """Represents an active production function that likely superseded a dead symbol."""
    symbol_name: str
    file_path: str
    line_number: int
    similarity: float
    code_snippet: str

    @property
    def qualified_id(self) -> str:
        return f"{self.file_path}:{self.symbol_name}"


def _tokenize_code(text: str) -> list[str]:
    """
    Split code text into normalized sub-words and identifiers.
    Handles snake_case and camelCase (e.g., 'legacy_tax_calculator' -> 'legacy', 'tax', 'calculator').
    """
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    subwords: list[str] = []
    for token in tokens:
        subwords.append(token)
        for part in token.split("_"):
            if len(part) >= 3:
                subwords.append(part)
    return subwords


def calculate_code_similarity(text1: str, text2: str) -> float:
    """
    Calculate cosine vector similarity between two code snippets.
    Returns a score between 0.00 (completely unrelated) and 1.00 (identical).
    """
    vec1 = Counter(_tokenize_code(text1))
    vec2 = Counter(_tokenize_code(text2))

    common_tokens = set(vec1.keys()) & set(vec2.keys())
    dot_product = sum(vec1[token] * vec2[token] for token in common_tokens)

    magnitude1 = math.sqrt(sum(count**2 for count in vec1.values()))
    magnitude2 = math.sqrt(sum(count**2 for count in vec2.values()))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return round(dot_product / (magnitude1 * magnitude2), 2)


def find_superseded_replacements(
    candidate_symbol: str,
    candidate_code: str,
    code_chunks: list[CodeChunk],
    top_k: int = 3,
    threshold: float = 0.35,
) -> list[ReplacementMatch]:
    """
    Search the repository's active code chunks to find functions that semantically
    replace the dead candidate symbol.

    Excludes the candidate itself from matching.
    """
    matches: list[ReplacementMatch] = []
    search_query = f"{candidate_symbol}\n{candidate_code}"

    for chunk in code_chunks:
        # Never match a symbol with itself
        if chunk.qualified_id == candidate_symbol:
            continue

        chunk_text = f"{chunk.symbol_name}\n{chunk.code}"
        similarity = calculate_code_similarity(search_query, chunk_text)

        if similarity >= threshold:
            matches.append(
                ReplacementMatch(
                    symbol_name=chunk.symbol_name,
                    file_path=chunk.file_path,
                    line_number=chunk.line_number,
                    similarity=similarity,
                    code_snippet=chunk.code,
                )
            )

    # Sort best matches first (highest similarity)
    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches[:top_k]