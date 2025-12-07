"""
Local AI Filtering
==================

This module provides local, CPU-based semantic filtering using `sentence-transformers`.
It is used to shortlist relevant articles before sending them to the LLM, saving API quota.
"""
import logging
from typing import List, Dict, Any
from urllib.parse import urlparse

try:
    from sentence_transformers import SentenceTransformer, util
    import torch
except ImportError:
    # Fallback for environments where dependencies might be missing during initial setup
    SentenceTransformer = None
    util = None

from .utils import get_logger

logger = get_logger(__name__)

class LocalFilter:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalFilter, cls).__new__(cls)
        return cls._instance

    def load_model(self, model_name: str = "all-MiniLM-L6-v2"):
        """Loads the sentence-transformer model (singleton)."""
        if self._model is None:
            if SentenceTransformer is None:
                logger.error("sentence-transformers not installed. Skipping local filtering.")
                return None
            
            logger.info(f"Loading local embedding model ({model_name})...")
            # Use CPU for GitHub Actions compatibility/cost
            device = 'cpu'
            if torch.cuda.is_available():
                device = 'cuda'
            elif torch.backends.mps.is_available():
                 device = 'mps'
                 
            self._model = SentenceTransformer(model_name, device=device)
            logger.info(f"Model loaded on {device}")
        return self._model

    def filter_by_relevance(self, items: List[Dict[str, Any]], topics: List[str], model_name: str = "all-MiniLM-L6-v2", limit: int = 20, threshold: float = 0.15, max_per_source: int = 5) -> List[Dict[str, Any]]:
        """
        Filters items by semantic relevance to topics, enforcing source diversity.
        """
        if not items or not topics:
            return items

        model = self.load_model(model_name)
        if not model:
            logger.warning("Local model unavailable. returning original items.")
            return items[:limit]

        logger.info(f"Local AI analyzing {len(items)} items against topics: {topics}")

        # 1. Encode Topics
        topic_embeddings = model.encode(topics, convert_to_tensor=True)

        # 2. Encode Items (Title + Summary)
        # Limit text length for speed
        item_texts = [f"{item.get('title', '')} {item.get('summary', '')}"[:512] for item in items]
        item_embeddings = model.encode(item_texts, convert_to_tensor=True)

        # 3. Compute Similarity details
        # We want the max similarity of an item to ANY of the provided topics
        cosine_scores = util.cos_sim(item_embeddings, topic_embeddings) 
        # cosine_scores shape: [train_initials, len(topics)]
        
        # Take the maximum score across all topics for each item
        max_scores, _ = cosine_scores.max(dim=1)

        # 4. Rank and Filter with Diversity
        scored_items = []
        for i, score in enumerate(max_scores):
            if score.item() >= threshold:
                scored_items.append((score.item(), items[i]))
        
        # Sort by score descending
        scored_items.sort(key=lambda x: x[0], reverse=True)
        
        logger.info(f"Found {len(scored_items)} items above threshold {threshold}")
        
        # 5. Diversity Loop
        final_items = []
        source_counts = {}
        
        for score, item in scored_items:
            if len(final_items) >= limit:
                break
                
            link = item.get("link", "")
            try:
                domain = urlparse(link).netloc
            except:
                domain = "unknown"
            
            # Check diversity constraint
            current_count = source_counts.get(domain, 0)
            if current_count < max_per_source:
                final_items.append(item)
                source_counts[domain] = current_count + 1
            else:
                logger.debug(f"Skipping {item.get('title')} from {domain} (Max {max_per_source} reached)")

        logger.info(f"Selected {len(final_items)} diverse, relevant items")
        return final_items
