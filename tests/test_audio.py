import pytest
from unittest.mock import patch, MagicMock
from src.audio import text_to_speech
from google.cloud import texttospeech

@pytest.fixture
def mock_tts_client():
    with patch('src.audio.texttospeech.TextToSpeechClient') as mock:
        client_instance = mock.return_value
        # Configure the response to have bytes content
        response = MagicMock()
        response.audio_content = b"fake_audio_bytes"
        client_instance.synthesize_speech.return_value = response
        yield mock

def test_voice_selection_wavenet_default(mock_tts_client):
    """Test that default voice type is WaveNet"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3") # Default
    
    # Check calls to synthesize_speech
    assert mock_instance.synthesize_speech.called
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Wavenet" in voice_params.name
    assert "Wavenet" in voice_params.name

def test_voice_selection_neural(mock_tts_client):
    """Test that voice_type='neural' selects Neural2 voices"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="neural")
    
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Neural2" in voice_params.name

def test_voice_selection_studio(mock_tts_client):
    """Test that voice_type='studio' selects Studio voices"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="studio")
    
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Studio" in voice_params.name

def test_voice_selection_chirp3_hd(mock_tts_client):
    """Test that voice_type='chirp3-hd' selects Chirp3 HD voices"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="chirp3-hd")
    
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Fenrir" in voice_params.name



def test_voice_selection_input_format(mock_tts_client):
    """Test that chirp3-hd uses plain text and others use SSML"""
    mock_instance = mock_tts_client.return_value
    
    # Test Chirp3-HD (Plain Text)
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="chirp3-hd")
    call_args = mock_instance.synthesize_speech.call_args
    # Check that 'text' arg is present and 'ssml' is not (or None)
    # Check that 'ssml' arg is present
    synthesis_input = call_args.kwargs['input']
    assert synthesis_input.ssml != ""
    assert not synthesis_input.text
    
    # Test Wavenet (SSML)
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="wavenet")
    call_args = mock_instance.synthesize_speech.call_args
    synthesis_input = call_args.kwargs['input']
    assert synthesis_input.ssml != ""
    assert not synthesis_input.text

def test_voice_selection_explicit_wavenet(mock_tts_client):
    """Test explicit 'wavenet' selection"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="wavenet")
    
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Wavenet" in voice_params.name
