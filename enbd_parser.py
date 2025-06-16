import pdfplumber
import json
from datetime import datetime
import re
from typing import Dict, List, Any
import os

def categorize(description: str) -> str:
    """Categorize transaction based on description."""
    desc = description.lower()
    if any(x in desc for x in ['restaurant', 'talabat', 'kfc', 'hardees', 'soho garden', 'gazebo', 'tasty pizza', 
                              'pulao', 'shake', 'cafe', 'noon minutes', 'wakha', 'meraki', 'hot n spicy', 'pak darbar',
                              'apna kabab', 'mcdonalds', 'carrefour food', 'fillicafe']):
        return "Food & Dining"
    if any(x in desc for x in ['taxi', 'careem', 'zo feur', 'dubai taxi', 'emarat', 'epcco', 'enoc', 
                              'car rental', 'hala']):
        return "Transport" 
    if any(x in desc for x in ['noon.com', 'carrefour', 'home centre', 'pakistan supermarket', 'supermarket',
                              'minutes', 'apple.com', 'itunes', 'openai', 'netflix', 'cursor']):
        return "Shopping"
    if any(x in desc for x in ['platiniumlist', 'reel entertainment', 'soho garden', 'expedia', 'leisure',
                              'mmall', 'smart dubai government']):
        return "Entertainment"
    if any(x in desc for x in ['dewa', 'electricity', 'smart dubai', 'etisalat', 'du', 'swyp']):
        return "Utilities"
    if any(x in desc for x in ['salon', 'barber', 'dry clean', 'laundry', 'spa']):
        return "Personal Care"
    if any(x in desc for x in ['openai', 'netflix', 'whoop', 'cursor', 'apple', 'itunes', 'chatgpt']):
        return "Subscription/Online"
    return "Others"

def determine_transaction_type(amount: float, description: str) -> str:
    """Determine if transaction is income or expense based on amount and description."""
    desc = description.lower()
    
    # For credit card statements: positive amounts are expenses, negative amounts are credits/income
    if amount > 0:
        # Positive amounts are typically expenses (charges on credit card)
        return "Expense"
    else:
        # Negative amounts are typically income/credits (payments, refunds, cashbacks)
        return "Income"

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
                        amount_float = float(amount.replace(',', ''))
                        transaction_type = determine_transaction_type(amount_float, description)
                        transaction = {
                            'date': date,
                            'description': description.strip(),
                            'amount': amount_float,
                            'type': transaction_type,
                            'category': categorize(description)
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

        # Segregate transactions by type
        income_transactions = [txn for txn in self.transactions if txn['type'] == 'Income']
        expense_transactions = [txn for txn in self.transactions if txn['type'] == 'Expense']

        # Calculate financial summary for credit card statement
        total_income = sum(abs(txn['amount']) for txn in income_transactions)  # Credits/payments (show as positive)
        total_expense = sum(txn['amount'] for txn in expense_transactions)  # Charges (already positive)
        net_balance = total_income - total_expense  # Net payment vs charges

        # Prepare the final output
        result = {
            'statement_info': self.statement_info,
            'transactions': self.transactions,
            'summary': {
                'total_income': round(total_income, 2),
                'total_expense': round(total_expense, 2),  
                'net_balance': round(net_balance, 2),
                'income_count': len(income_transactions),
                'expense_count': len(expense_transactions),
                'total_transactions': len(self.transactions)
            },
            'income_transactions': income_transactions,
            'expense_transactions': expense_transactions,
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
