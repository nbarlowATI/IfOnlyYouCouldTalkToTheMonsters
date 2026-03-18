import io
import random
import wave
import pygame as pg

from doomsettings import SAMPLE_RATE

class SoundEffect:

    def __init__(self, name, engine):
        byte_data = engine.wad_data.sound_effects[name]
        num_samples = byte_data[1] + (byte_data[2] << 8)
        self.raw_samples = byte_data[8:8 + num_samples]
        pg.mixer.init()
        self.wav_buffer = self.convert_to_wav()

    def convert_to_wav(self):
        # Convert to a WAV in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(1)  # 8-bit unsigned
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(self.raw_samples)

        wav_buffer.seek(0)
        return wav_buffer
    
    def play(self):
        wav_buffer = self.convert_to_wav()
        sound = pg.mixer.Sound(wav_buffer)
        sound.play()

    def play_pitched(self, pitch_factor=1.0):
        """Play with pitch shifted by pitch_factor (e.g. 1.1 = 10% higher)."""
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(1)
            wf.setframerate(int(SAMPLE_RATE * pitch_factor))
            wf.writeframes(self.raw_samples)
        buf.seek(0)
        pg.mixer.Sound(buf).play()

    def play_random_pitch(self, variance=0.1):
        """Play with pitch randomised ± variance (default ±10%)."""
        self.play_pitched(random.uniform(1.0 - variance, 1.0 + variance))

