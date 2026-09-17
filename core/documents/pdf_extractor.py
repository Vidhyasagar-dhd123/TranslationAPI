# PDF extraction operations

from PyPDF2 import PdfReader
import os

class PDFExtractor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.reader = PdfReader(file_path)

    def extract_text(self,page_number=0):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")
        
        text_content = ""
        if page_number < 0 or page_number >= len(self.reader.pages):
            raise ValueError("Invalid page number.")
        page = self.reader.pages[page_number]
        text_content = page.extract_text()
        return text_content.strip()
