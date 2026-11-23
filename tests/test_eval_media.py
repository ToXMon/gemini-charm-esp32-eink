import tempfile
import unittest
import wave
from pathlib import Path
from PIL import Image
from evals.check_media import inspect

class MediaChecksTests(unittest.TestCase):
    def test_image_and_audio(self):
        with tempfile.TemporaryDirectory() as d:
            image=Path(d)/'image.jpg'; Image.new('RGB',(135,240)).save(image)
            self.assertEqual(inspect(image,'image')['height'],240)
            audio=Path(d)/'audio.wav'
            with wave.open(str(audio),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(bytes(3200))
            self.assertAlmostEqual(inspect(audio,'audio')['duration_seconds'],.1)
            data=audio.read_bytes();audio.write_bytes(data[:-100])
            with self.assertRaises(ValueError): inspect(audio,'audio')

if __name__=='__main__':unittest.main()
