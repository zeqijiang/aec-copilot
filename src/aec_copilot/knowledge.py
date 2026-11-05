"""Local few-shot retrieval plus an optional LightRAG HTTP adapter.

The local index is dependency-free and reproducible. It is not represented as
LightRAG; production semantic retrieval requires the user's LightRAG service.
"""
from __future__ import annotations

import json
import math
import os
import re
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _tokens(text: str) -> list[str]:
    latin=re.findall(r"[a-zA-Z0-9_.]+",text.lower())
    chinese=re.findall(r"[\u4e00-\u9fff]",text)
    bigrams=["".join(chinese[i:i+2]) for i in range(max(0,len(chinese)-1))]
    return latin+chinese+bigrams


@dataclass
class KnowledgeHit:
    id: str
    instruction: str
    score: float
    plan: dict[str, Any]
    source: str


class LocalKnowledgeBase:
    def __init__(self,path: str | Path) -> None:
        self.path=Path(path)
        self.records=[]
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record=json.loads(line)
                    if isinstance(record,dict) and record.get("instruction") and isinstance(record.get("plan"),dict): self.records.append(record)

    def search(self,query: str,limit: int = 3,min_score: float = 0.08) -> list[KnowledgeHit]:
        q=Counter(_tokens(query)); qnorm=math.sqrt(sum(v*v for v in q.values())) or 1
        hits=[]
        for index,record in enumerate(self.records):
            tokens=Counter(_tokens(record["instruction"]))
            dot=sum(min(count,tokens.get(token,0))*count for token,count in q.items())
            # Weighted overlap with query-length normalization; deterministic ties.
            norm=math.sqrt(sum(v*v for v in tokens.values())) or 1
            score=dot/(qnorm*norm)
            if score>=min_score:
                hits.append(KnowledgeHit(id=str(record.get("id",index)),instruction=record["instruction"],score=round(score,6),plan=record["plan"],source="local-jsonl"))
        hits.sort(key=lambda h:(-h.score,h.id))
        return hits[:max(0,min(limit,10))]

    def prompt_examples(self,query: str,limit: int = 3) -> str:
        return "\n".join(json.dumps({"instruction":h.instruction,"plan":h.plan},ensure_ascii=False) for h in self.search(query,limit))


class LightRAGClient:
    """Read-only adapter. Endpoint/response shape must be checked against deployment."""

    def __init__(self,base_url: str | None = None,api_key: str | None = None) -> None:
        self.base=(base_url or os.getenv("LIGHTRAG_BASE_URL","")).rstrip("/")
        self.api_key=api_key or os.getenv("LIGHTRAG_API_KEY","")

    @property
    def configured(self) -> bool: return bool(self.base)

    def query(self,text: str,mode: str = "hybrid") -> dict[str, Any]:
        if not self.configured: raise RuntimeError("LIGHTRAG_BASE_URL is not configured")
        body=json.dumps({"query":text,"mode":mode,"include_references":True}).encode()
        headers={"Content-Type":"application/json"}
        if self.api_key: headers["Authorization"]=f"Bearer {self.api_key}"
        request=urllib.request.Request(f"{self.base}/query",data=body,headers=headers)
        with urllib.request.urlopen(request,timeout=60) as response: return json.load(response)
