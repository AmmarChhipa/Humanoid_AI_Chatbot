from TTS.api import TTS

# List available models
tts = TTS()
print(tts.list_models())

# Load a specific model (create a new TTS instance)
model_tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=True, gpu=False)

# Use the model to speak
model_tts.tts_to_file(text="Hello, I am your humanoid assistant!", file_path="output.wav")
