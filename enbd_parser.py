import pdfplumber
import json
from datetime import datetime
import re
from typing import Dict, List, Any
import os

class ENBDStatementParser:
    def __init__(self, pdf_path: str, password: str = None):
        self.pdf_path = pdf_path
        self.password = password
        self.transactions = []
        self.statement_info = {}
        
    def extract_text(self) -> List[str]:
        """Extract text from all pages of the PDF."""
        with pdfplumber.open(self.pdf_path, password=self.password) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return pages

    def parse_statement_info(self, text: str) -> None:
        """Parse basic statement information."""
        # Try to find statement period
        period_match = re.search(r'Statement Period:?\s*(.+)', text, re.IGNORECASE)
        if period_match:
            self.statement_info['statement_period'] = period_match.group(1).strip()

        # Try to find card number (masking for security)
        card_match = re.search(r'Card Number:?\s*([X\d\s-]+)', text, re.IGNORECASE)
        if card_match:
            self.statement_info['card_number'] = card_match.group(1).strip()

    def parse_transactions(self, pages: List[str]) -> None:
        """Parse transactions from the statement."""
        for page in pages:
            # Split the page into lines
            lines = page.split('\n')
            
            for line in lines:
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Try to match transaction patterns
                # This pattern needs to be adjusted based on the actual format of your statement
                # Example pattern for date, description, and amount
                transaction_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([-\d,.]+)\s*$', line)
                
                if transaction_match:
                    date, description, amount = transaction_match.groups()
                    try:
                        amount = float(amount.replace(',', ''))
                        transaction = {
                            'date': date,
                            'description': description.strip(),
                            'amount': amount
                        }
                        self.transactions.append(transaction)
                    except ValueError:
                        continue

    def parse(self) -> Dict[str, Any]:
        """Main parsing function."""
        pages = self.extract_text()
        if not pages:
            raise ValueError("No text could be extracted from the PDF")

        # Parse statement information from the first page
        self.parse_statement_info(pages[0])
        
        # Parse transactions from all pages
        self.parse_transactions(pages)

        # Prepare the final output
        result = {
            'statement_info': self.statement_info,
            'transactions': self.transactions,
            'metadata': {
                'parsed_at': datetime.now().isoformat(),
                'source_file': os.path.basename(self.pdf_path)
            }
        }
        
        return result

def parse_statement(pdf_path: str, output_path: str = None, password: str = None) -> Dict[str, Any]:
    """
    Parse an ENBD bank statement and optionally save to JSON file.
    
    Args:
        pdf_path (str): Path to the PDF file
        output_path (str, optional): Path to save the JSON output
        password (str, optional): Password for protected PDF file
        
    Returns:
        Dict containing the parsed statement data
    """
    parser = ENBDStatementParser(pdf_path, password)
    result = parser.parse()
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    
    return result

if __name__ == "__main__":
    import sys
    import getpass
    
    if len(sys.argv) < 2:
        print("Usage: python enbd_parser.py <pdf_file> [output_json_file]")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # Prompt for password if needed
        try:
            with pdfplumber.open(pdf_file) as pdf:
                pass
            password = None
        except:
            password = getpass.getpass("Enter PDF password: ")
            
        result = parse_statement(pdf_file, output_file, password)
        if not output_file:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
