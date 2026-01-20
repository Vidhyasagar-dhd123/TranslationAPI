import sys
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, BitsAndBytesConfig
from transformers.utils import is_flash_attn_2_available, is_flash_attn_greater_or_equal_2_10
from IndicTransToolkit.processor import IndicProcessor
from nltk import sent_tokenize
from indicnlp.tokenize.sentence_tokenize import sentence_split, DELIM_PAT_NO_DANDA
from transformers import GenerationConfig


class BatchTranslation:
    def __init__(self, model_dir, device='cpu', batch_size=4,quantization='',attn_implementation='eager'):
        self.model_dir = model_dir
        self.device = device
        self.batch_size = batch_size
        self.processor = IndicProcessor(inference=True)
        self.flores_codes = {
            "asm_Beng": "as",
            "awa_Deva": "hi",
            "ben_Beng": "bn",
            "bho_Deva": "hi",
            "brx_Deva": "hi",
            "doi_Deva": "hi",
            "eng_Latn": "en",
            "gom_Deva": "kK",
            "guj_Gujr": "gu",
            "hin_Deva": "hi",
            "hne_Deva": "hi",
            "kan_Knda": "kn",
            "kas_Arab": "ur",
            "kas_Deva": "hi",
            "kha_Latn": "en",
            "lus_Latn": "en",
            "mag_Deva": "hi",
            "mai_Deva": "hi",
            "mal_Mlym": "ml",
            "mar_Deva": "mr",
            "mni_Beng": "bn",
            "mni_Mtei": "hi",
            "npi_Deva": "ne",
            "ory_Orya": "or",
            "pan_Guru": "pa",
            "san_Deva": "hi",
            "sat_Olck": "or",
            "snd_Arab": "ur",
            "snd_Deva": "hi",
            "tam_Taml": "ta",
            "tel_Telu": "te",
            "urd_Arab": "ur",
        }

        if quantization == '4-bit':
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_type=torch.float16
            )
        elif quantization == '8-bit':
            bnb_config = BitsAndBytesConfig(
                load_in_8bit=True,
                bnb_4bit_use_double_quant= True,
                bnb_4bit_compute_type=torch.float16
            )
        else:
            bnb_config = None

        if attn_implementation == 'flash_attention_2':
            if is_flash_attn_2_available() and is_flash_attn_greater_or_equal_2_10():
                attn_implementation = 'flash_attention_2'
            else:
                print("Flash Attention v2 is not available. Falling back to eager attention.")
                attn_implementation = 'eager'

        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            self.model_dir,
            trust_remote_code=True,
            attn_implementation=attn_implementation,
            quantization_config=bnb_config,
            low_cpu_mem_usage=True,
            local_files_only=False
        ).to(device)

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_dir,
            trust_remote_code=True,
            local_files_only=False
        )

        if bnb_config is None and device == 'cuda':
            self.model.half()

        self.model.config.use_cache = True
        self.model.eval()
        
    def batch_translate(self, input_sentences, src_lang, tgt_lang):
        translations = []

        gen_config = GenerationConfig(
            max_new_tokens=256,
            num_beams=1,
            min_length=0,
            do_sample=False,
            use_cache=False
        )

        if src_lang == tgt_lang:
            return input_sentences
        
        if src_lang not in self.flores_codes or tgt_lang not in self.flores_codes:
            print(f"Source language ({src_lang}) or target language ({tgt_lang}) not supported.")
            return [""] * len(input_sentences)

        for i in range(0, len(input_sentences), self.batch_size):
            batch_sentences = input_sentences[i:i + self.batch_size]
            batch_sentences = self.processor.preprocess_batch(batch_sentences, src_lang=src_lang, tgt_lang = tgt_lang)

            inputs = self.tokenizer(
                batch_sentences,
                return_tensors="pt",
                padding="longest",
                truncation=True,
                return_attention_mask=True,
            ).to(self.device)

            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    generation_config=gen_config,
                    use_cache=False,
                    num_beams=1,
                    max_length=256,
                    early_stopping=True,
                )

            decoded_outputs = self.tokenizer.batch_decode(
                generated_ids,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )

            translations += self.processor.postprocess_batch(decoded_outputs,lang=tgt_lang)

            del inputs
            torch.cuda.empty_cache()
        return translations
    
        
    def split_sentences(self,input_text, lang):
        if lang == "eng_Latn":
            input_sentences = sent_tokenize(input_text)
            sents_nltk = sent_tokenize(input_text)
            input_sentences = sents_nltk
            input_sentences = [sent.replace("\xad", "") for sent in input_sentences]
        else:
            input_sentences = sentence_split(
                input_text, lang=self.flores_codes[lang], delim_pat=DELIM_PAT_NO_DANDA
            )
        return input_sentences
    
    
    def translate_paragraph(self, input_text, src_lang, tgt_lang):
        input_sentences = self.split_sentences(input_text, src_lang)
        translated_text = self.batch_translate(input_sentences, src_lang, tgt_lang)
        return " ".join(translated_text)