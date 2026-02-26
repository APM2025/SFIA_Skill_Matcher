import requests
import PyPDF2
from pathlib import Path

def download_and_extract(url, pdf_path, text_path):
    print(f"Downloading {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    
    with open(pdf_path, 'wb') as f:
        f.write(response.content)
    
    print(f"Saved to {pdf_path}. Extracting text...")
    
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for i, page in enumerate(reader.pages):
            text += f"\\n--- PAGE {i+1} ---\\n"
            text += page.extract_text() + "\\n"
            
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(text)
        
    print(f"Saved extracted text to {text_path}")
    
if __name__ == "__main__":
    download_and_extract(
        'https://www.engc.org.uk/media/a1yfae02/uk-spec-fourth-edition.pdf',
        'uk_spec.pdf',
        'uk_spec_extracted.txt'
    )
