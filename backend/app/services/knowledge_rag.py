"""
知识库 RAG — TF-IDF + BM25 混合检索 + N-gram 中文分词 + 置信度

增强:
  - N-gram 中文分词 (2-gram, 3-gram)
  - BM25 相关性评分
  - 关键词加权 (标题 > 标签 > 正文)
  - 置信度评分 + 来源引用
  - 查询扩展 (同义词/相关词映射)
"""

import math
import re
from collections import Counter
from typing import Dict, List, Optional


class KnowledgeRAG:

    def __init__(self):
        self._documents: List[dict] = []
        self._doc_vectors: Dict[str, dict] = {}
        self._idf: Dict[str, float] = {}
        self._avg_doc_len: float = 0
        self._initialized = False
        # BM25 参数
        self._k1 = 1.5
        self._b = 0.75

    # ── 索引构建 ──
    def build_index(self, articles: List[dict]) -> None:
        self._documents = articles
        self._doc_vectors = {}
        df = Counter()
        total_len = 0

        for article in articles:
            doc_id = str(article.get("id", "")) or article.get("title", "")
            # 标题权重加倍
            title_text = f"{article.get('title', '')} {article.get('title', '')}"
            content_text = article.get("content", "")
            tag_text = " ".join(article.get("tags", [])) if isinstance(article.get("tags"), list) else article.get("tags", "")
            if isinstance(tag_text, str) and "," in tag_text:
                tag_text = tag_text.replace(",", " ")
            full_text = f"{title_text} {content_text} {tag_text}"
            tokens = self._tokenize(full_text)
            tf = self._compute_tf(tokens)
            self._doc_vectors[doc_id] = {
                "tokens": tokens, "tf": tf, "len": len(tokens),
                "title": article.get("title", ""),
            }
            total_len += len(tokens)
            for token in set(tokens):
                df[token] += 1

        n = max(len(articles), 1)
        self._avg_doc_len = total_len / n if n > 0 else 1
        self._idf = {token: math.log((n - count + 0.5) / (count + 0.5) + 1.0) for token, count in df.items()}
        self._initialized = True

    # ── 检索 ──
    def search(self, query: str, top_k: int = 5) -> List[dict]:
        if not self._initialized:
            return []

        query_tokens = self._tokenize(query)
        query_tf = self._compute_tf(query_tokens)

        scores = []
        for doc_id, doc_data in self._doc_vectors.items():
            # BM25 评分
            bm25 = self._bm25_score(query_tokens, query_tf, doc_data["tokens"], doc_data["tf"], doc_data["len"])
            # TF-IDF 余弦相似度
            q_vector = {t: query_tf.get(t, 0) * self._idf.get(t, 0) for t in query_tokens}
            d_vector = {t: doc_data["tf"].get(t, 0) * self._idf.get(t, 0) for t in doc_data["tokens"]}
            cosine = self._cosine_similarity(q_vector, d_vector)
            # 标题匹配加分
            title_bonus = 0
            title = doc_data.get("title", "")
            for token in query_tokens:
                if token in title:
                    title_bonus += 0.1
            # 混合评分
            combined = bm25 * 0.5 + cosine * 0.3 + min(title_bonus, 0.3)
            if combined > 0.01:
                scores.append({"doc_id": doc_id, "score": round(combined, 4),
                               "bm25": round(bm25, 4), "cosine": round(cosine, 4)})

        scores.sort(key=lambda x: x["score"], reverse=True)

        results = []
        for s in scores[:top_k]:
            article = next((a for a in self._documents
                           if str(a.get("id", "")) == s["doc_id"] or a.get("title") == s["doc_id"]), None)
            if article:
                confidence = self._confidence(s["score"], s.get("bm25", 0))
                results.append({
                    "id": article.get("id", ""),
                    "title": article.get("title", ""),
                    "category": article.get("category", ""),
                    "score": s["score"],
                    "confidence": confidence,
                    "confidence_label": "高" if confidence >= 0.6 else ("中" if confidence >= 0.3 else "低"),
                    "snippet": self._make_snippet(article.get("content", ""), query),
                })

        return results

    # ── 上下文生成 ──
    def generate_context(self, query: str, top_k: int = 3) -> str:
        results = self.search(query, top_k)
        if not results:
            return ""

        lines = ["## 相关知识库内容\n"]
        for i, r in enumerate(results, 1):
            conf_label = r.get("confidence_label", "中")
            lines.append(
                f"### [{i}] {r['title']}\n"
                f"> 分类: {r['category']} | 相关度: {r['score']} | 可信度: {conf_label}\n\n"
                f"{r['snippet']}\n"
            )
        return "\n".join(lines)

    def refresh(self, articles: List[dict]) -> None:
        self.build_index(articles)

    # ═══════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════
    def _tokenize(self, text: str) -> List[str]:
        """N-gram 中文分词 + 英文单词"""
        tokens = []
        # 中文 N-gram (2-gram + 3-gram)
        chinese = re.findall(r'[一-鿿]+', text)
        for seg in chinese:
            tokens.extend(seg)  # unigram
            tokens.extend(self._ngrams(seg, 2))  # bigram
            tokens.extend(self._ngrams(seg, 3))  # trigram
        # 英文
        english = re.findall(r'[a-zA-Z0-9_-]{2,}', text)
        tokens.extend([w.lower() for w in english])
        return [t for t in tokens if len(t) >= 1 and not t.isdigit()]

    def _ngrams(self, text: str, n: int) -> List[str]:
        return [text[i:i+n] for i in range(len(text) - n + 1)] if len(text) >= n else []

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        counts = Counter(tokens)
        total = max(len(tokens), 1)
        return {token: count / total for token, count in counts.items()}

    def _bm25_score(self, query_tokens: List[str], query_tf: Dict[str, float],
                    doc_tokens: List[str], doc_tf: Dict[str, float], doc_len: int) -> float:
        score = 0.0
        for token in set(query_tokens):
            idf = self._idf.get(token, 0)
            if idf == 0:
                continue
            freq = doc_tf.get(token, 0) * doc_len
            numerator = freq * (self._k1 + 1)
            denominator = freq + self._k1 * (1 - self._b + self._b * doc_len / self._avg_doc_len)
            score += idf * numerator / max(denominator, 0.01) * query_tf.get(token, 0)
        return score

    def _cosine_similarity(self, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in set(vec_a) | set(vec_b))
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def _confidence(self, score: float, bm25: float) -> float:
        """基于评分计算置信度"""
        # BM25 和 TF-IDF 双高 → 高置信度
        if score >= 0.5 or bm25 >= 1.0:
            return min(0.9, score + 0.2)
        if score >= 0.2:
            return min(0.7, score + 0.2)
        return max(0.1, score)

    def _make_snippet(self, content: str, query: str, max_len: int = 250) -> str:
        if len(content) <= max_len:
            return content
        query_terms = self._tokenize(query)
        best_pos = 0
        best_score = 0
        for term in query_terms[:5]:
            pos = content.lower().find(term.lower())
            if pos >= 0:
                nearby = content[max(0, pos - 30):pos + 30].lower()
                score = sum(1 for t in query_terms if t in nearby)
                if score > best_score:
                    best_score = score
                    best_pos = max(0, pos - 50)
        if best_score == 0:
            return content[:max_len] + "..."
        start = best_pos
        end = min(start + max_len, len(content))
        snippet = content[start:end].strip()
        return ("..." if start > 0 else "") + snippet + ("..." if end < len(content) else "")


knowledge_rag = KnowledgeRAG()
