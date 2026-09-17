"""
OCR Adapter for extracting text from images inside PDF documents using pytesseract and PIL.
"""
import io
import logging
from typing import List, Tuple
from PIL import Image

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

logger = logging.getLogger(__name__)


class OCRAdapter:
    @staticmethod
    def process_images(image_bytes_list: List[bytes], lang: str = "eng") -> List[dict]:
        """
        Processes a list of image bytes, extracts image properties, runs OCR,
        and returns detailed dictionaries for each image.
        """
        if not image_bytes_list:
            return []

        results = []
        for idx, img_bytes in enumerate(image_bytes_list, start=1):
            ocr_text = ""
            width, height = 0, 0
            img_format = "PNG"

            try:
                img = Image.open(io.BytesIO(img_bytes))
                width, height = img.size
                img_format = img.format or "PNG"

                if PYTESSERACT_AVAILABLE:
                    try:
                        text = pytesseract.image_to_string(img, lang=lang)
                        if text and text.strip():
                            ocr_text = text.strip()
                    except pytesseract.TesseractNotFoundError:
                        logger.warning("Tesseract binary not found in PATH. OCR skipped.")
                        ocr_text = "(Image detected - Tesseract binary not configured on host)"
                    except Exception as ocr_err:
                        logger.warning(f"OCR processing failed for image {idx}: {ocr_err}")
                        ocr_text = f"(OCR extraction failed: {str(ocr_err)})"
                else:
                    ocr_text = "(Pytesseract library not available)"
            except Exception as img_err:
                logger.warning(f"Failed to open image {idx}: {img_err}")
                continue

            results.append({
                "image_index": idx,
                "bytes": img_bytes,
                "format": img_format.lower(),
                "width": width,
                "height": height,
                "size_bytes": len(img_bytes),
                "ocr_text": ocr_text,
            })

        return results

    @staticmethod
    def extract_text_from_images(image_bytes_list: List[bytes], lang: str = "eng") -> Tuple[str, int]:
        """
        Legacy helper returning (combined_ocr_text, count).
        """
        processed = OCRAdapter.process_images(image_bytes_list, lang)
        if not processed:
            return "", 0

        ocr_parts = [
            f"[Image {item['image_index']} OCR Text]:\n{item['ocr_text']}"
            for item in processed if item['ocr_text']
        ]
        return "\n\n".join(ocr_parts).strip(), len(processed)

