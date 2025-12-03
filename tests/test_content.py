import pytest
from unittest.mock import MagicMock, patch
from src.content import filter_by_semantics

def test_filter_by_semantics():
    items = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
    
    with patch("src.content.genai") as mock_genai:
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.return_value.text = "[0, 2]"
        
        filtered = filter_by_semantics(items, ["topic"], "model")
        
        assert len(filtered) == 2
        assert filtered[0]["title"] == "A"
        assert filtered[1]["title"] == "C"
