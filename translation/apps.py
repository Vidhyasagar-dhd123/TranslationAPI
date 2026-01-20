from django.apps import AppConfig


class TranslationConfig(AppConfig):
    name = 'translation'

    translator = None

    def ready(self):
        if not TranslationConfig.translator:
            print("\n\nLoading model...")
            from translation.batch_translation import BatchTranslation
            import torch
            TranslationConfig.translator = BatchTranslation("ai4bharat/indictrans2-en-indic-dist-200M","cuda" if torch.cuda.is_available() else "cpu")