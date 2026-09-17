"""
Translation Engine Adapter wrapping AI4Bharat IndicTrans2 models.
Supports batch paragraph translation, Flores code mapping, and fallback mock modes.
"""
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class TranslationEngineAdapter:
    _instance: Optional['TranslationEngineAdapter'] = None
    _lock = threading.Lock()

    def __init__(self, model_name: str = "ai4bharat/indictrans2-en-indic-dist-200M", use_gpu: bool = True):
        self.model_name = model_name
        self.use_gpu = use_gpu
        self._translator = None
        self._is_initialized = False

    @classmethod
    def get_instance(cls) -> 'TranslationEngineAdapter':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = TranslationEngineAdapter()
        return cls._instance

    def _initialize_model(self):
        if self._is_initialized:
            return

        with self._lock:
            if self._is_initialized:
                return
            try:
                import torch
                from translation.batch_translation import BatchTranslation
                device = "cuda" if (self.use_gpu and torch.cuda.is_available()) else "cpu"
                logger.info(f"Initializing IndicTrans2 model '{self.model_name}' on device '{device}'...")
                self._translator = BatchTranslation(
                    model_dir=self.model_name,
                    device=device,
                    batch_size=4
                )
                self._is_initialized = True
                logger.info("IndicTrans2 model initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to load IndicTrans2 model: {e}. Running in fallback mode.")
                self._translator = None
                self._is_initialized = True

    def translate_paragraph(self, text: str, source_lang: str = "eng_Latn", target_lang: str = "hin_Deva",
                            src_lang: str = None, tgt_lang: str = None) -> str:
        s_lang = src_lang or source_lang
        t_lang = tgt_lang or target_lang

        if not text or not text.strip():
            return ""

        if s_lang == t_lang:
            return text

        self._initialize_model()

        if self._translator is not None:
            try:
                return self._translator.translate_paragraph(text, src_lang=s_lang, tgt_lang=t_lang)
            except Exception as e:
                logger.warning(f"IndicTrans2 translation failed: {e}. Using fallback translator.")

        # Fallback translation if model weights are not loaded/offline
        return self._mock_translate(text, s_lang, t_lang)

    def _mock_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Graceful fallback when model is downloading or running in non-GPU test environment.
        """
        return f"[Translated ({source_lang} -> {target_lang})]: {text}"

