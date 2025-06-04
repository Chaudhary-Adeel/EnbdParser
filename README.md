# ENBD Statement Parser
# Muhammad Adeel | Chaudhary1337@gmail.com

This tool parses ENBD (Emirates NBD) bank credit card statements from PDF format into structured JSON data.

## Setup

1. Create a virtual environment and activate it:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

You can use the parser in two ways:

1. From the command line:
```bash
python enbd_parser.py input.pdf output.json
```
or to print to console:
```bash
python enbd_parser.py input.pdf
```

2. As a Python module:
```python
from enbd_parser import parse_statement

# Parse and save to file
result = parse_statement('input.pdf', 'output.json')

# Or parse and get the data as a dictionary
result = parse_statement('input.pdf')
```

## Output Format

The parser generates JSON with the following structure:
```json
{
  "statement_info": {
    "statement_period": "...",
    "card_number": "..."
  },
  "transactions": [
    {
      "date": "DD/MM/YYYY",
      "description": "...",
      "amount": 0.00
    }
  ],
  "metadata": {
    "parsed_at": "...",
    "source_file": "..."
  }
}
```

## Note

This parser is designed specifically for ENBD credit card statements. The accuracy of the parsing depends on the consistency of the PDF format. Please verify the output data.
